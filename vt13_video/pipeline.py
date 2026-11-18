"""End-to-end VT13 USB -> HEVC -> BGR frame pipeline."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import logging
from pathlib import Path
import subprocess
import threading
import time
from .config import AppConfig
from .control import ControlLink
from .decoder import Frame, FrameQueue, HevcDecoder
from .nal import (
    AccessUnit,
    AccessUnitAssembler,
    AnnexBParser,
    NALUnit,
    PARAMETER_SET_TYPES,
    ParameterSetCache,
)
from .recovery import RecoveryController
from .sources import ByteSource, ReadResult, ReadTimeout, SourceError, VT13UsbSource
from .stats import StreamStats


_KEYFRAME_HINT_AFTER_S = 10.0
_ERROR_LOG_INTERVAL_S = 5.0


class _DgBitReader:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def u(self, n: int) -> int:
        value = 0
        for _ in range(n):
            value = (value << 1) | ((self.data[self.pos >> 3] >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return value

    def ue(self) -> int:
        zeros = 0
        while self.u(1) == 0:
            zeros += 1
            if zeros > 31:
                raise ValueError("bad ue")
        return (1 << zeros) - 1 + (self.u(zeros) if zeros else 0)


def _dg_unescape(payload: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(payload):
        if i + 2 < len(payload) and payload[i] == 0 and payload[i + 1] == 0 and payload[i + 2] == 3:
            out += b"\x00\x00"
            i += 3
        else:
            out.append(payload[i])
            i += 1
    return bytes(out)


def _dg_parse_sps_log2(payload: bytes):
    r = _DgBitReader(_dg_unescape(payload))
    r.u(4)
    max_sub = r.u(3)
    r.u(1)
    r.u(2); r.u(1); r.u(5); r.u(32)
    r.u(1); r.u(1); r.u(1); r.u(1)
    r.u(44); r.u(8)
    prof = []
    for _ in range(max_sub):
        prof.append((r.u(1), r.u(1), r.u(1)))
    if max_sub > 0:
        for _ in range(max_sub, 8):
            r.u(2)
    for present, _lvl, _ in prof:
        if present:
            r.u(88)
    r.ue()
    chroma = r.ue()
    if chroma == 3:
        r.u(1)
    r.ue(); r.ue()
    if r.u(1):
        for _ in range(4):
            r.ue()
    r.ue(); r.ue()
    return r.ue() + 4


def _dg_parse_pps(payload: bytes):
    r = _DgBitReader(_dg_unescape(payload))
    r.ue(); r.ue()
    r.u(1)
    output_flag = r.u(1)
    extra = r.u(3)
    return output_flag, extra


def _dg_parse_poc(payload: bytes, nal_type: int, log2: int, pps):
    output_flag, extra = pps
    r = _DgBitReader(_dg_unescape(payload[:64]))
    if not r.u(1):
        return None
    if 16 <= nal_type <= 23:
        r.u(1)
    r.ue()
    for _ in range(extra):
        r.u(1)
    r.ue()
    if output_flag:
        r.u(1)
    if nal_type not in (19, 20):
        return r.u(log2)
    return 0


class RecordingError(RuntimeError):
    """Raised when a requested recording output cannot be created."""


class VT13Stream:
    """Run the USB read/decode loop in a background thread.

    Frames are exposed through a bounded queue (``read_frame`` / ``latest_frame``)
    or through ``frames()``.  The pipeline never sends vendor-specific USB OUT
    requests; recovery is limited to re-claiming the IN endpoint and optional
    device reset/clear-halt as configured.  With ``control.enabled`` it also
    writes DUML I-frame requests and pairing queries to the CDC control port.
    """

    def __init__(
        self,
        config: AppConfig,
        source: ByteSource | None = None,
        logger: logging.Logger | None = None,
        control: ControlLink | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("vt13_video.pipeline")
        self.source = source or VT13UsbSource(config.device, config.read, self.logger)
        self._control = control
        self._control_owned = control is None
        self.parser = AnnexBParser()
        self.assembler = AccessUnitAssembler()
        self.params = ParameterSetCache()
        import os as _dg_os
        self._dg_enabled = _dg_os.environ.get("VT13_DAMAGE_GATE", "0") == "1"
        self._dg_log2 = None
        self._dg_pps = None
        self._dg_expected = None
        self._dg_skip = False
        self._dg_gaps = 0
        if config.decoder.parameter_sets_file is not None:
            try:
                self.params.load_file(config.decoder.parameter_sets_file)
                self.logger.info(
                    "loaded parameter sets from %s (%d bytes)",
                    config.decoder.parameter_sets_file,
                    len(self.params.bootstrap_bytes()),
                )
            except Exception as exc:
                self.logger.warning(
                    "could not load parameter sets from %s: %r",
                    config.decoder.parameter_sets_file,
                    exc,
                )
        if config.decoder.backend == "ffmpeg-pipe":
            from .ffmpeg_pipe import FfmpegPipeDecoder

            self.decoder = FfmpegPipeDecoder(config.decoder, self.logger)
        elif config.decoder.backend == "worker":
            from .worker_client import WorkerDecoder

            self.decoder = WorkerDecoder(
                config.decoder,
                self.logger,
                on_recover=lambda: self._request_iframe("worker_recover"),
            )
        else:
            self.decoder = HevcDecoder(config.decoder, self.logger)
        self.frames = FrameQueue(config.decoder.queue_size, config.decoder.drop_oldest)
        self.stats = StreamStats()
        self.recovery = RecoveryController(config.recovery)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._source_open = False
        self._last_read_at: float | None = None
        self._last_data_at: float | None = None
        self._waiting_data_since: float | None = None
        self._waiting_logged = False
        self._data_logged = False
        self._irap_seen_since_reset = False
        self._keyframe_started_since_reset = False
        self._parameter_sets_logged = False
        self._parameter_types_since_save: set[int] = set()
        self._parameter_wait_logged = False
        self._keyframe_hint_logged = False
        self._disconnect_recovery_pending = False
        self._reopened_after_disconnect = False
        self._last_error_log_at: float | None = None
        self._last_logged_error_kind: str | None = None
        self._suppressed_error_logs = 0
        self._save_first_done = False
        self._saved_parameter_sets_path: Path | None = None
        self._last_saved_parameter_bytes: bytes | None = None
        self._next_iframe_at = 0.0
        self._last_frame_at: float | None = None
        self._last_vcl_au_at: float | None = None
        self._decode_started_at: float | None = None
        self._data_epoch_started_at: float | None = None
        self._stall_resets = 0
        self._kernel_abort_event = threading.Event()
        self._kernel_watcher: subprocess.Popen | None = None
        self._kernel_watcher_thread: threading.Thread | None = None

        self._record_fh = None
        self._times_fh = None
        self._events_fh = None

    # ------------------------------------------------------------------ lifecycle
    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self.stats.start()
        self.stats.device_identity = self.source.identity
        if self.config.control.enabled and self._control is None:
            try:
                self._control = ControlLink(self.config.control, self.logger)
                self._control_owned = True
                self._control.start()
            except Exception as exc:
                self.logger.warning("control link disabled after setup failure: %r", exc)
                self._control = None
        self._start_kernel_watch()
        self._open_recording()
        self._thread = threading.Thread(target=self._run, name="vt13-video", daemon=True)
        self._thread.start()

    def stop(self, wait: bool = True, timeout: float | None = None) -> None:
        self._stop_event.set()
        if wait:
            if timeout is None:
                timeout = max(2.0, self.config.read.timeout_ms / 1000.0 + 2.0)
            self.join(timeout)

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    def wait(self, timeout: float | None = None) -> None:
        self.join(timeout)

    def __enter__(self) -> "VT13Stream":
        self.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.stop()

    # ------------------------------------------------------------------ frame API
    def read_frame(self, timeout: float | None = None) -> Frame | None:
        return self.frames.get(timeout)

    @property
    def latest_frame(self) -> Frame | None:
        return self.frames.latest

    def snapshot(self) -> dict:
        self.stats.dropped_frames = self.frames.dropped
        result = self.stats.snapshot()
        status = self._call_source("status_snapshot")
        if isinstance(status, dict):
            result["usb"]["status_drain"] = status
        result["decoder"] = self.decoder.snapshot()
        result["decode"]["corrupt_frames"] = self.decoder.corrupt_frames
        parameter_sets = self.params.snapshot()
        parameter_sets["saved"] = self._saved_parameter_sets_path is not None
        parameter_sets["saved_path"] = (
            str(self._saved_parameter_sets_path)
            if self._saved_parameter_sets_path is not None
            else None
        )
        result["parameter_sets"] = parameter_sets
        seconds_since_data = result["usb"]["seconds_since_data"]
        result["link"] = {
            "usb_open": self._source_open,
            "data_flowing": bool(
                self._source_open
                and self._data_logged
                and seconds_since_data is not None
                and seconds_since_data <= self.config.read.stall_timeout_s
            ),
            "parameter_sets_complete": bool(parameter_sets["complete"]),
            "irap_seen": self._irap_seen_since_reset,
            "keyframe_started": self._keyframe_started_since_reset,
            "streaming": result["state"] == "streaming",
        }
        result["recovery"] = asdict(self.recovery.snapshot())
        result["control"] = (
            self._control.snapshot() if self._control is not None else {"enabled": False}
        )
        result["watchdog"] = {"output_stall_resets": self._stall_resets}
        result["source"] = self.source.identity
        result["queue"] = {"size": self.frames.qsize(), "dropped": self.frames.dropped}
        return result

    def status_line(self) -> str:
        line = self.stats.status_line()
        if self.decoder.corrupt_frames:
            line += f", {self.decoder.corrupt_frames} corrupt"
        stats = self.stats.snapshot()
        seconds_since_data = stats["usb"]["seconds_since_data"]
        data_flowing = bool(
            self._source_open
            and self._data_logged
            and seconds_since_data is not None
            and seconds_since_data <= self.config.read.stall_timeout_s
        )
        line += (
            f" | usb={'up' if self._source_open else 'down'}"
            f", data={'yes' if data_flowing else 'no'}"
            f", params={'yes' if self.params.complete else 'no'}"
            f", irap={'yes' if self._irap_seen_since_reset else 'no'}"
            f", keyframe={'yes' if self._keyframe_started_since_reset else 'no'}"
        )
        if self._control is not None:
            ctrl = self._control.snapshot()
            line += f", ctrl=tx{ctrl['tx_frames']}/rx{ctrl['rx_frames']}"
            if ctrl.get("iframe_requests"):
                line += f"/idr{ctrl['iframe_requests']}"
        if self._stall_resets:
            line += f", stall_resets={self._stall_resets}"
        return line

    # ------------------------------------------------------------------ main loop
    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                self._check_kernel_abort()
                now = time.monotonic()
                if self.config.runtime.max_seconds > 0:
                    started = self.stats.started_at or now
                    if now - started >= self.config.runtime.max_seconds:
                        self.stats.set_state("stopped", "duration reached")
                        break

                if not self._source_open:
                    if not self._open_source(now):
                        continue

                try:
                    result = self.source.read()
                except ReadTimeout as exc:
                    self.stats.record_timeout()
                    now = time.monotonic()
                    last_data = self._last_data_at if self._last_data_at is not None else now
                    if now - last_data >= self.config.read.stall_timeout_s:
                        self._recover("stall", str(exc), now, exc)
                    continue
                except SourceError as exc:
                    self._recover(exc.kind, str(exc), time.monotonic(), exc)
                    continue
                except Exception as exc:
                    self._recover("unknown", repr(exc), time.monotonic(), exc)
                    continue

                if result.eof:
                    self.stats.set_state("eof", "end of capture")
                    break
                if not result.data:
                    self._handle_empty_read(time.monotonic())
                    continue
                self._handle_chunk(result)
                if self.recovery.on_read_success(result.received_at):
                    if self._suppressed_error_logs:
                        self.logger.info(
                            "USB stream recovered after a failure streak "
                            "(%d repeated failure details suppressed)",
                            self._suppressed_error_logs,
                        )
                    else:
                        self.logger.info("USB stream recovered after a failure streak")
                    self._suppressed_error_logs = 0
                    self._last_error_log_at = None
                    self._last_logged_error_kind = None
                    if self.decoder.needs_keyframe:
                        self._refresh_waiting_state(result.received_at)
                    else:
                        self.stats.set_state("streaming")
        finally:
            self._finish()

    def _open_source(self, now: float) -> bool:
        try:
            # BEGIN VT13_ASYNC_USB_EXPERIMENT
            import os
            if os.environ.get("VT13_ASYNC_USB", "0") == "1":
                from .async_usb import AsyncBufferedSource
                if not isinstance(self.source, AsyncBufferedSource):
                    self.source = AsyncBufferedSource(
                        self.source,
                        max_chunks=int(os.environ.get("VT13_ASYNC_CHUNKS", "16384")),
                    )
            # END VT13_ASYNC_USB_EXPERIMENT
            self.source.open()
        except Exception as exc:
            message = f"cannot open USB source: {exc}"
            self.stats.set_state("waiting_device", message)
            self.stats.record_error("open", message, now)
            delay = self.recovery.on_error(now, "open")
            self._event("open_failed", message)
            self.logger.warning("%s; retrying in %.2fs", message, delay)
            if not self.config.recovery.enabled:
                self.stats.set_state("error", message)
                self._stop_event.set()
                return False
            self._stop_event.wait(delay)
            return False

        self._source_open = True
        self._last_read_at = None
        self._last_data_at = time.monotonic()
        self._waiting_data_since = None
        self._keyframe_hint_logged = False
        reopened_after_disconnect = self._disconnect_recovery_pending
        self._disconnect_recovery_pending = False
        self._reopened_after_disconnect = reopened_after_disconnect
        self.recovery.on_open_success(self._last_data_at)
        self.stats.device_identity = self.source.identity
        self.stats.set_state("open", self.source.identity)
        self._event("open", self.source.identity)
        self.logger.info("USB source open: %s", self.source.identity)
        if reopened_after_disconnect:
            self._event("usb_reopened", self.source.identity)
            self.logger.info(
                "USB re-enumerated after a disconnect; the VT03 encoder was not reset. "
                "Waiting for a fresh IRAP"
            )

        preroll = self._call_source("drain", self.config.read.drain_reads)
        if isinstance(preroll, (bytes, bytearray)) and preroll:
            data = bytes(preroll)
            self._event("preroll", f"{len(data)} bytes")
            self._handle_chunk(ReadResult(data, time.monotonic()))
        elif isinstance(preroll, int) and preroll:
            # Backwards compatibility for sources that still discard pre-roll.
            self._event("drain", f"{preroll} bytes")
        return True

    def _recover(
        self,
        kind: str,
        message: str,
        now: float,
        exc: BaseException | None = None,
    ) -> None:
        errno = getattr(exc, "errno", None) if exc is not None else None
        backend_code = getattr(exc, "backend_error_code", None) if exc is not None else None
        context = self.stats.read_context()
        since_data = (
            None
            if self._last_data_at is None
            else max(0.0, now - self._last_data_at)
        )
        self.stats.record_error(
            kind,
            message,
            now,
            errno=errno,
            backend_error_code=backend_code,
            reads=context["reads"],
            bytes_read=context["bytes"],
            since_data_s=since_data,
        )
        since_text = "unknown" if since_data is None else f"{since_data:.3f}s"
        detail = (
            f"{kind}: {message}; errno={errno}; backend={backend_code}; "
            f"last_reads={context['reads']}; last_bytes={context['bytes']}; "
            f"since_data={since_text}"
        )
        self.stats.set_state("recovering", detail)
        self._event("usb_error", detail)
        report_error = self._should_log_read_failure(kind, now)
        if report_error:
            self.logger.warning("USB read failure (%s): %s", kind, detail)
        else:
            self.logger.debug("USB read failure (%s): %s", kind, detail)

        if not self.config.recovery.enabled:
            self.stats.set_state("error", f"{kind}: {message}")
            self._stop_event.set()
            return

        if kind == "disconnected":
            self._disconnect_recovery_pending = True

        delay = self.recovery.on_error(now, f"{kind}: {message}")

        halt_ok = False
        if self.config.recovery.clear_halt_on_error and kind in {"pipe", "stall", "io"}:
            halt_ok = bool(self._call_source("clear_halt"))
            self.stats.record_halt_clear(halt_ok)
            self._event("clear_halt", f"ok={halt_ok}")
            if halt_ok:
                if report_error:
                    self.logger.info("clear_halt after %s: ok", kind)
                else:
                    self.logger.debug("clear_halt after %s: ok", kind)
            else:
                self.logger.warning("clear_halt after %s: failed", kind)

        reset_attempted = self.recovery.should_reset()
        if reset_attempted:
            reset_ok = bool(self._call_source("reset_device"))
            if reset_ok:
                self.stats.record_reset()
            self.recovery.mark_reset()
            self._event("usb_reset", f"ok={reset_ok}")

        self.stats.record_recovery()
        if kind == "io" and halt_ok and not reset_attempted:
            self._event("recovery_in_place", f"usb_{kind}")
            if report_error:
                self.logger.info(
                    "endpoint halt cleared after io; preserving stream and decoder state"
                )
            else:
                self.logger.debug(
                    "endpoint halt cleared after io; preserving stream and decoder state"
                )
            if self.decoder.needs_keyframe:
                self._refresh_waiting_state(now)
            else:
                self.stats.set_state("streaming")
            return

        self._mark_discontinuity(f"usb_{kind}", log=report_error)
        if halt_ok and not reset_attempted:
            self._event("recovery_in_place", f"usb_{kind}")
            if report_error:
                self.logger.info(
                    "endpoint halt cleared; continuing on the existing USB handle"
                )
            else:
                self.logger.debug(
                    "endpoint halt cleared; continuing on the existing USB handle"
                )
            return

        self._close_source()
        self.logger.warning("reopening USB in %.2fs after %s", delay, kind)
        self._stop_event.wait(delay)

    def _handle_empty_read(self, now: float) -> None:
        self.stats.record_empty_read()
        last_data = self._last_data_at if self._last_data_at is not None else now
        elapsed = max(0.0, now - last_data)
        if elapsed >= self.config.read.stall_timeout_s:
            self._recover("stall", f"no data for {elapsed:.3f}s", now)
        else:
            self._refresh_waiting_state(now)

    def _should_log_read_failure(self, kind: str, now: float) -> bool:
        if kind == "disconnected":
            self._last_error_log_at = now
            self._last_logged_error_kind = kind
            return True
        if (
            self._last_error_log_at is None
            or kind != self._last_logged_error_kind
            or now - self._last_error_log_at >= _ERROR_LOG_INTERVAL_S
        ):
            if self._suppressed_error_logs:
                self.logger.warning(
                    "suppressed %d repeated USB failure details",
                    self._suppressed_error_logs,
                )
            self._suppressed_error_logs = 0
            self._last_error_log_at = now
            self._last_logged_error_kind = kind
            return True
        self._suppressed_error_logs += 1
        return False

    @staticmethod
    def _is_kernel_abort_line(line: str) -> bool:
        return "HEVC_LCU_CHECK status=0xf" in line or "Aborting decoding session" in line

    def _start_kernel_watch(self) -> None:
        if not self.config.recovery.kernel_abort_watch:
            return
        try:
            proc = subprocess.Popen(
                ["journalctl", "-k", "-f", "-o", "cat", "--since", "now"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as exc:
            self.logger.warning("kernel abort watch unavailable: %r", exc)
            return
        self._kernel_watcher = proc
        self._kernel_watcher_thread = threading.Thread(
            target=self._kernel_watch_loop, args=(proc,), name="vt13-kernel-watch", daemon=True
        )
        self._kernel_watcher_thread.start()
        self.logger.info("kernel abort watch enabled (journalctl -k -f)")

    def _kernel_watch_loop(self, proc: subprocess.Popen) -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                if self._stop_event.is_set():
                    break
                if self._is_kernel_abort_line(line):
                    self._kernel_abort_event.set()
        except Exception as exc:
            if not self._stop_event.is_set():
                self.logger.debug("kernel abort watch stopped: %r", exc)

    def _check_kernel_abort(self) -> None:
        if not self._kernel_abort_event.is_set():
            return
        self._kernel_abort_event.clear()
        if self.decoder.needs_keyframe:
            return
        self.logger.warning("kernel VDEC abort detected; resetting decoder immediately")
        self._event("kernel_abort", "0xf")
        self._mark_discontinuity("kernel_0xf")

    def _stop_kernel_watch(self) -> None:
        proc = self._kernel_watcher
        self._kernel_watcher = None
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        thread = self._kernel_watcher_thread
        self._kernel_watcher_thread = None
        if thread is not None:
            thread.join(timeout=2.0)

    def _data_flowing(self, now: float) -> bool:
        return bool(
            self._source_open
            and self._last_data_at is not None
            and now - self._last_data_at <= self.config.read.stall_timeout_s
        )

    def _request_iframe(self, reason: str) -> None:
        control = self._control
        if control is None or not self.config.control.iframe_on_recovery:
            return
        now = time.monotonic()
        if now < self._next_iframe_at:
            return
        if not self._data_flowing(now):
            return
        if control.request_iframe(reason):
            self._event("control_iframe", reason)
        self._next_iframe_at = now + max(self.config.control.iframe_retry_s, 0.5)

    def _mark_discontinuity(self, reason: str, *, log: bool = True) -> None:
        self.parser.reset()
        self.assembler.reset()
        self.decoder.reset()
        self.stats.record_decoder_reset()
        self.stats.record_discontinuity(reason)
        self.stats.set_state("waiting_keyframe", reason)
        self._waiting_logged = False
        self._keyframe_hint_logged = False
        self._parameter_wait_logged = False
        self._parameter_types_since_save.clear()
        self._waiting_data_since = None
        self._irap_seen_since_reset = False
        self._keyframe_started_since_reset = False
        self._event("discontinuity", reason)
        self._last_frame_at = None
        self._last_vcl_au_at = None
        self._decode_started_at = None
        self._data_epoch_started_at = time.monotonic()
        if self.config.control.iframe_on_recovery:
            self._request_iframe("discontinuity")
        if log:
            self.logger.warning(
                "stream discontinuity (%s); waiting for a fresh VPS/SPS/PPS + IRAP",
                reason,
            )
        else:
            self.logger.debug(
                "stream discontinuity (%s); waiting for a fresh VPS/SPS/PPS + IRAP",
                reason,
            )

    def _handle_chunk(self, result: ReadResult) -> None:
        now = result.received_at
        if self._last_read_at is not None:
            gap = (
                result.source_gap_s
                if result.source_gap_s is not None
                else now - self._last_read_at
            )
            if gap > self.config.read.stall_timeout_s:
                self._data_epoch_started_at = now
            if gap > self.config.recovery.gap_threshold_s:
                reason = f"read_gap_{gap:.3f}s"
                if self.config.recovery.reset_on_gap:
                    self._mark_discontinuity(reason)
                else:
                    self.stats.record_discontinuity(reason)
                    self._event("read_gap", reason)
                    self.logger.warning(
                        "USB read gap of %.3fs; continuing without a forced reset "
                        "(set recovery.reset_on_gap=true to resync immediately)",
                        gap,
                    )
        self._last_read_at = now
        self._last_data_at = now
        if self._waiting_data_since is None:
            self._waiting_data_since = now

        self.stats.record_read(len(result.data), now)
        if not self._data_logged:
            self.logger.info("USB link is up: receiving video data")
            self._data_logged = True
        self._write_record(result.data, now)
        nals = self.parser.feed(result.data)
        for nal in nals:
            self._process_nal(nal, now)
        self._refresh_waiting_state(now)
        self._check_output_stall(now)

    def _process_nal(self, nal: NALUnit, now: float) -> None:
        self.stats.record_nal(nal)
        self.params.update(nal)
        if nal.is_parameter_set:
            self._parameter_types_since_save.add(nal.nal_type)
            if self.params.complete and not self._parameter_sets_logged:
                self.logger.info("parameter sets complete: VPS/SPS/PPS")
                self._parameter_sets_logged = True
            if self.params.complete and self._parameter_types_since_save.issuperset(
                PARAMETER_SET_TYPES
            ):
                if self._save_parameter_sets():
                    self._parameter_types_since_save.clear()
        for au in self.assembler.feed(nal, now):
            self._handle_au(au, now)

    def _save_parameter_sets(self) -> bool:
        path = self.config.decoder.save_parameter_sets
        if path is None or not self.params.complete:
            return True
        data = self.params.bootstrap_bytes()
        if data == self._last_saved_parameter_bytes:
            return True
        try:
            saved = self.params.write_file(path)
        except (OSError, ValueError) as exc:
            self.logger.warning("could not save parameter sets to %s: %r", path, exc)
            return False
        self._last_saved_parameter_bytes = data
        self._saved_parameter_sets_path = saved
        self.logger.info("saved parameter sets to %s (%d bytes)", saved, len(data))
        self._event("parameter_sets_saved", str(saved))
        return True

    def _refresh_waiting_state(self, now: float | None = None) -> None:
        if not self.decoder.needs_keyframe:
            return
        now = time.monotonic() if now is None else now
        # A missing-parameter state is more specific than a generic keyframe
        # wait, so keep it until the cache becomes complete while still emitting
        # the actionable hint below.
        if not (self.stats.state == "waiting_parameter_sets" and not self.params.complete):
            self.stats.set_state("waiting_keyframe", "no usable IRAP yet")
        if not self._keyframe_hint_logged:
            waiting_since = self._waiting_data_since
            data_flowing = waiting_since is not None and self._data_flowing(now)
            if (
                data_flowing
                and waiting_since is not None
                and now - waiting_since >= _KEYFRAME_HINT_AFTER_S
            ):
                if self._reopened_after_disconnect:
                    if self.params.complete:
                        action = (
                            "power-cycle VT03 or relink its wireless video link; "
                            "re-plugging only the VT13 USB does not reset VT03"
                        )
                    else:
                        action = (
                            "power-cycle VT03 or relink its wireless video link for "
                            "fresh VPS/SPS/PPS + IRAP; re-plugging only the VT13 USB "
                            "does not reset VT03"
                        )
                elif self.params.complete:
                    action = "power-cycle VT03 to emit a fresh IRAP"
                else:
                    action = "power-cycle VT03 to emit fresh VPS/SPS/PPS + IRAP"
                self.logger.warning(
                    "USB link is receiving data but decoding has not started; %s "
                    "(params=%s, irap=%s)",
                    action,
                    "complete" if self.params.complete else "missing",
                    "seen" if self._irap_seen_since_reset else "not seen",
                )
                self._keyframe_hint_logged = True
        if (
            self._control is not None
            and self.config.control.iframe_on_recovery
            and self.config.control.iframe_retry_s > 0
            and now >= self._next_iframe_at
            and self._data_flowing(now)
        ):
            self._request_iframe("waiting_keyframe")

    def _check_output_stall(self, now: float) -> None:
        threshold = self.config.decoder.stall_restart_s
        if threshold <= 0 or self.decoder.needs_keyframe:
            return
        if self._last_vcl_au_at is None:
            return
        if now - self._last_vcl_au_at > max(1.0, self.config.read.stall_timeout_s):
            return
        reference = max(
            (
                value
                for value in (
                    self._last_frame_at,
                    self._decode_started_at,
                    self._data_epoch_started_at,
                )
                if value is not None
            ),
            default=None,
        )
        if reference is None or now - reference < threshold:
            return
        stalled = now - reference
        self._stall_resets += 1
        self.logger.warning(
            "no decoded output for %.2fs while VCL access units are arriving; "
            "resetting the decoder and requesting an I-frame",
            stalled,
        )
        self._event("output_stall", f"{stalled:.3f}s")
        self._mark_discontinuity("output_stall")


    def _dg_should_skip(self, au: AccessUnit) -> bool:
        if not self._dg_enabled:
            return False
        for nal in au.nals:
            if nal.nal_type == 33:
                try:
                    self._dg_log2 = _dg_parse_sps_log2(nal.payload)
                except Exception:
                    self._dg_log2 = None
            elif nal.nal_type == 34:
                try:
                    self._dg_pps = _dg_parse_pps(nal.payload)
                except Exception:
                    self._dg_pps = None
        if self._dg_log2 is None or self._dg_pps is None:
            return False
        vcl = next((n for n in au.nals if n.is_vcl), None)
        if vcl is None:
            return False
        try:
            if au.has_irap:
                self._dg_skip = False
                self._dg_expected = _dg_parse_poc(vcl.payload, vcl.nal_type, self._dg_log2, self._dg_pps)
                return False
            if self._dg_skip:
                return True
            poc = _dg_parse_poc(vcl.payload, vcl.nal_type, self._dg_log2, self._dg_pps)
            if poc is None:
                return False
            if self._dg_expected is not None:
                mask = (1 << self._dg_log2) - 1
                if ((poc - self._dg_expected) & mask) != 1:
                    self._dg_skip = True
                    self._dg_gaps += 1
                    if self._dg_gaps <= 20 or self._dg_gaps % 50 == 0:
                        self.logger.warning(
                            "damage gate: POC %s -> %s discontinuity; skipping GOP until next IRAP (gap #%d)",
                            self._dg_expected, poc, self._dg_gaps,
                        )
                    return True
            self._dg_expected = poc
            return False
        except Exception:
            return False

    def _handle_au(self, au: AccessUnit, now: float) -> None:
        self.stats.record_au(au)
        # BEGIN VT13_DAMAGE_GATE
        if self._dg_should_skip(au):
            self.stats.record_skipped_au()
            return
        # END VT13_DAMAGE_GATE
        # BEGIN VT13_SHED_TO_IRAP
        # Opt-in load shedding: keep/skip whole GOPs so the decode path can
        # keep up with a higher source rate without touching USB reads.
        import os as _vt13_shed_os
        if _vt13_shed_os.environ.get("VT13_SHED_TO_IRAP", "0") == "1":
            if au.has_irap:
                _keep_n = max(1, int(_vt13_shed_os.environ.get("VT13_SHED_KEEP", "1")))
                _skip_n = max(0, int(_vt13_shed_os.environ.get("VT13_SHED_SKIP", "1")))
                _idx = getattr(self, "_vt13_shed_gop", -1) + 1
                self._vt13_shed_gop = _idx
                _cycle = _keep_n + _skip_n
                self._vt13_shed_keep = (_idx % _cycle) < _keep_n
            if not getattr(self, "_vt13_shed_keep", True):
                self.stats.record_skipped_au()
                return
        # END VT13_SHED_TO_IRAP
        # BEGIN VT13_LOW_LATENCY_CATCHUP_V2
        # Preserve raw USB/NAL parsing, but do not waste CPU decoding stale AUs.
        # Skipped HEVC AUs require a fresh IRAP before decoding can resume.
        import os as _vt13_ll_os
        _vt13_ll_ms = float(_vt13_ll_os.environ.get("VT13_LOW_LATENCY_MS", "0"))
        if _vt13_ll_ms > 0:
            _vt13_ll_age = max(0.0, time.monotonic() - au.received_at)
            _vt13_ll_limit = _vt13_ll_ms / 1000.0
            _vt13_ll_active = getattr(self, "_vt13_ll_catching_up", False)
            if _vt13_ll_age > _vt13_ll_limit or (
                _vt13_ll_active and _vt13_ll_age > _vt13_ll_limit * 0.5
            ):
                if not _vt13_ll_active:
                    self._vt13_ll_catching_up = True
                    self.decoder.reset()
                    self._keyframe_started_since_reset = False
                    self._irap_seen_since_reset = False
                    self._waiting_logged = False
                    self.logger.warning(
                        "LOW LATENCY catch-up: AU age %.2fs exceeds %.2fs; "
                        "skipping decode of stale AUs (not USB bytes), then "
                        "waiting for a FRESH IRAP",
                        _vt13_ll_age, _vt13_ll_limit,
                    )
                    self.stats.set_state("catching_up", "discarding stale decode work")
                self.stats.record_skipped_au()
                return
            if _vt13_ll_active:
                self._vt13_ll_catching_up = False
                self.logger.warning(
                    "LOW LATENCY caught up: AU age %.2fs; "
                    "decode will resume on next IRAP (relink VT03 if none arrives)",
                    _vt13_ll_age,
                )
                self.stats.set_state("waiting_keyframe", "low-latency resync")
        # END VT13_LOW_LATENCY_CATCHUP_V2
        if not au.has_vcl:
            return
        self._last_vcl_au_at = now
        if au.has_irap:
            self._irap_seen_since_reset = True

        bootstrap = b""
        starting_keyframe = False
        if self.decoder.needs_keyframe:
            if not au.has_irap:
                self.stats.record_skipped_au()
                self._refresh_waiting_state(now)
                if not self._waiting_logged:
                    self.logger.info(
                        "waiting for IRAP: %d NALs / %d access units seen, none random-access",
                        self.stats.nals,
                        self.stats.aus,
                    )
                    self._waiting_logged = True
                return
            if not au.has_all_parameter_sets:
                if not self.params.complete:
                    self.stats.record_skipped_au()
                    missing = ", ".join(self.params.snapshot()["missing"])
                    self.stats.set_state("waiting_parameter_sets", missing)
                    self._event("waiting_parameter_sets", missing)
                    if not self._parameter_wait_logged:
                        self.logger.info(
                            "IRAP received but parameter sets incomplete: missing %s",
                            missing,
                        )
                        self._parameter_wait_logged = True
                    return
                bootstrap = self.params.bootstrap_bytes()
            starting_keyframe = True
            self.logger.info("IRAP received; starting decoder")

        resets_before = self.decoder.resets
        errors_before = self.decoder.errors
        frames = self.decoder.decode(au, bootstrap)
        if self.decoder.errors > errors_before:
            self.stats.record_decode_error(self.decoder.errors - errors_before)
        if starting_keyframe and not self.decoder.needs_keyframe:
            self._keyframe_started_since_reset = True
            self._reopened_after_disconnect = False
            self._decode_started_at = now
            self.stats.record_keyframe_start()
            self.stats.set_state("streaming")
        if self.decoder.resets > resets_before:
            self.stats.record_decoder_reset()
            self.stats.set_state("waiting_keyframe", self.decoder.waiting_reason)
            self._waiting_logged = False
            self._waiting_data_since = None
            self._keyframe_hint_logged = False
            self._irap_seen_since_reset = False
            self._keyframe_started_since_reset = False
            self._last_frame_at = None
            self._last_vcl_au_at = None
            self._decode_started_at = None
            self._event("decoder_reset", self.decoder.waiting_reason or "")
            if self.config.control.iframe_on_recovery:
                self._request_iframe("decoder_reset")

        if frames:
            self._last_frame_at = now
            self.stats.set_state("streaming")
            self._waiting_logged = False
        for frame in frames:
            self.frames.put(frame)
            self.stats.record_frame(frame)
            self._maybe_save_first(frame)

    def _maybe_save_first(self, frame: Frame) -> None:
        path = self.config.output.save_first
        if path is None or self._save_first_done or frame.image is None:
            return
        try:
            import cv2

            path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(path), frame.image)
            self._save_first_done = True
            self.logger.info("saved first frame to %s (%dx%d)", path, frame.width, frame.height)
            self._event("first_frame", str(path))
        except Exception as exc:
            self.logger.warning("could not save first frame: %r", exc)

    # ------------------------------------------------------------------ recording
    def _open_recording(self) -> None:
        record = self.config.output.record
        if record is None:
            return
        try:
            record.parent.mkdir(parents=True, exist_ok=True)
            self._record_fh = record.open("wb")
            times_path = record.with_suffix(".times.tsv")
            self._times_fh = times_path.open("w", encoding="utf-8")
            events_path = record.with_name(record.stem + ".events.tsv")
            self._events_fh = events_path.open("w", encoding="utf-8")
            self._times_fh.write("elapsed_s\tchunk_length\twall_time_utc\n")
            self._events_fh.write("elapsed_s\tevent\tdetail\twall_time_utc\n")
        except OSError as exc:
            self._close_recording()
            message = (
                f"cannot create recording files at {record}: {exc}. "
                "Choose a writable --record path and directory."
            )
            self.stats.set_state("error", message)
            raise RecordingError(message) from exc
        self.logger.info("recording raw EP data to %s", record)

    def _write_record(self, data: bytes, now: float) -> None:
        if self._record_fh is None:
            return
        self._record_fh.write(data)
        elapsed = now - (self.stats.started_at or now)
        if self._times_fh is not None:
            wall_time = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            self._times_fh.write(f"{elapsed:.6f}\t{len(data)}\t{wall_time}\n")
        self.stats.record_recorded_bytes(len(data))

    def _event(self, kind: str, detail: str) -> None:
        if self._events_fh is None:
            return
        now = time.monotonic()
        elapsed = now - (self.stats.started_at or now)
        wall_time = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        self._events_fh.write(f"{elapsed:.6f}\t{kind}\t{detail}\t{wall_time}\n")

    def _close_recording(self) -> None:
        for handle in (self._record_fh, self._times_fh, self._events_fh):
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
        self._record_fh = None
        self._times_fh = None
        self._events_fh = None

    # ------------------------------------------------------------------ shutdown
    def _finish(self) -> None:
        try:
            now = time.monotonic()
            for nal in self.parser.flush():
                self._process_nal(nal, now)
            for au in self.assembler.flush():
                self._handle_au(au, now)
            for frame in self.decoder.flush():
                self.frames.put(frame)
                self.stats.record_frame(frame)
        except Exception as exc:
            self.logger.debug("final flush failed: %r", exc)
        self._close_source()
        self._close_control()
        self._stop_kernel_watch()
        self.stats.dropped_frames = self.frames.dropped
        if self.stats.state not in {"error", "eof", "stopped"}:
            self.stats.set_state("stopped")
        self._event("stop", self.stats.state)
        self._close_recording()

    def _close_source(self) -> None:
        if not self._source_open:
            return
        try:
            self.source.close()
        except Exception as exc:
            self.logger.debug("source close failed: %r", exc)
        finally:
            self._source_open = False
            self._data_logged = False
            self._waiting_data_since = None

    def _close_control(self) -> None:
        control = self._control
        if control is None or not self._control_owned:
            return
        try:
            control.close()
        except Exception as exc:
            self.logger.debug("control close failed: %r", exc)

    def _call_source(self, name: str, *args):
        method = getattr(self.source, name, None)
        if method is None:
            return None
        try:
            return method(*args)
        except Exception as exc:
            self.logger.debug("source.%s failed: %r", name, exc)
            return None
