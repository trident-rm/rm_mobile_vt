"""End-to-end VT13 USB -> HEVC -> BGR frame pipeline."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Iterator

from .config import AppConfig
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


class RecordingError(RuntimeError):
    """Raised when a requested recording output cannot be created."""


class VT13Stream:
    """Run the USB read/decode loop in a background thread.

    Frames are exposed through a bounded queue (``read_frame`` / ``latest_frame``)
    or through ``frames()``.  The pipeline never sends vendor-specific OUT
    requests; recovery is limited to re-claiming the IN endpoint and optional
    device reset/clear-halt as configured.
    """

    def __init__(
        self,
        config: AppConfig,
        source: ByteSource | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("vt13_video.pipeline")
        self.source = source or VT13UsbSource(config.device, config.read, self.logger)
        self.parser = AnnexBParser()
        self.assembler = AccessUnitAssembler()
        self.params = ParameterSetCache()
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

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ------------------------------------------------------------------ frame API
    def read_frame(self, timeout: float | None = None) -> Frame | None:
        return self.frames.get(timeout)

    @property
    def latest_frame(self) -> Frame | None:
        return self.frames.latest

    def frames_iter(self) -> Iterator[Frame]:
        while self.is_running or self.frames.qsize() > 0:
            frame = self.read_frame(0.5)
            if frame is not None:
                yield frame
            elif not self.is_running and self.frames.qsize() == 0:
                break

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
        return line

    # ------------------------------------------------------------------ main loop
    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
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
            data_flowing = (
                self._source_open
                and waiting_since is not None
                and self._last_data_at is not None
                and now - self._last_data_at <= self.config.read.stall_timeout_s
            )
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

    def _handle_au(self, au: AccessUnit, now: float) -> None:
        self.stats.record_au(au)
        if not au.has_vcl:
            return
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
            self._event("decoder_reset", self.decoder.waiting_reason or "")

        if frames:
            self.stats.set_state("streaming")
            self._waiting_logged = False
        for frame in frames:
            self.frames.put(frame)
            self.stats.record_frame(frame)
            self._maybe_save_first(frame)

    def _maybe_save_first(self, frame: Frame) -> None:
        path = self.config.output.save_first
        if path is None or self._save_first_done:
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

    def _call_source(self, name: str, *args):
        method = getattr(self.source, name, None)
        if method is None:
            return None
        try:
            return method(*args)
        except Exception as exc:
            self.logger.debug("source.%s failed: %r", name, exc)
            return None
