"""FFmpeg subprocess decode backend.

Hardware (or software) HEVC decode runs in a verified ffmpeg binary; decoded
NV12 frames are framed as rawvideo in a nut pipe so dynamic resolution
changes keep correct per-frame dimensions. A reader thread demuxes with PyAV
and converts via cv2 (NEON-optimized, ~7x faster than swscale to_ndarray on
Cortex-A53). Implements the HevcDecoder interface by subclassing it and
reusing its IRAP gating / error-reset state machine.
"""
from __future__ import annotations

import hashlib
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from typing import Any

from .config import DecoderConfig
from .decoder import DependencyError, Frame, HevcDecoder
from .nal import AccessUnit, scan_nals


class FfmpegPipeDecoder(HevcDecoder):
    """Decode via an external ffmpeg process over stdin/stdout pipes."""

    def __init__(self, config: DecoderConfig, logger: logging.Logger | None = None) -> None:
        self._proc: subprocess.Popen | None = None
        self._frame_q: queue.Queue = queue.Queue(maxsize=256)
        self._reader: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._reader_error: str | None = None
        self._au_context: AccessUnit | None = None
        self._pipe_dropped = 0
        self._terminated = False
        self._last_sps_hash: bytes | None = None
        self._display_proc: subprocess.Popen | None = None
        self._display_dims: tuple[int, int] | None = None
        self._display_disabled = False
        self._display_q: queue.Queue | None = None
        self._display_writer: threading.Thread | None = None
        self._display_stop = threading.Event()
        self._display_dropped = 0
        self._display_corrupt_dropped = 0
        self._display_green_dropped = 0
        self._display_grey_dropped = 0
        self._display_partial_green_dropped = 0
        try:
            _display_fps = float(os.environ.get("VT13_DISPLAY_FPS", "0") or 0)
        except ValueError:
            _display_fps = 0.0
        self._display_min_interval = (1.0 / _display_fps) if _display_fps > 0 else 0.0
        self._display_last_at = 0.0
        self._timing = os.environ.get("VT13_PIPE_TIMING", "0") == "1"
        self._t_wait = []
        self._t_disp = []
        self._t_bgr = []
        self._t_build = []
        self._t_log_at = 0.0
        super().__init__(config, logger)

    def _fps_mode_args(self, binary: str) -> list[str]:
        try:
            out = subprocess.run(
                [binary, "-version"], capture_output=True, text=True, timeout=10
            ).stdout
            major = int(out.split("version", 1)[1].strip().split(".", 1)[0].lstrip("n"))
        except Exception:
            major = 0
        if major >= 5:
            return ["-fps_mode", "passthrough"]
        return ["-vsync", "0"]

    def _new_context(self):
        try:
            import av  # noqa: F401
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except ImportError as exc:
            raise DependencyError(f"ffmpeg-pipe backend requires av, cv2, numpy: {exc}") from exc
        binary = self.config.ffmpeg_path or shutil.which("ffmpeg")
        if not binary:
            raise DependencyError("ffmpeg-pipe backend requires an ffmpeg binary (decoder.ffmpeg_path)")
        self._binary = binary
        self._frame_q = queue.Queue(maxsize=256)
        self._reader_error = None
        self._terminated = False
        self._raw_mode = os.environ.get("VT13_PIPE_TRANSPORT", "nut") == "raw"
        self._raw_dims = None
        self._raw_dims_ready = threading.Event()
        if self._raw_mode:
            _log_level = "info"
            _out_args = ["-pix_fmt", "nv12", "-c:v", "rawvideo", "-f", "rawvideo", "pipe:1"]
        else:
            _log_level = "warning"
            _out_args = ["-pix_fmt", "nv12", "-c:v", "rawvideo", "-flush_packets", "1", "-f", "nut", "pipe:1"]
        cmd = [
            binary, "-hide_banner", "-nostdin", "-loglevel", _log_level,
            "-c:v", self.config.ffmpeg_codec, "-f", "hevc", "-i", "pipe:0",
            "-map", "0:v:0", *self._fps_mode_args(binary), *_out_args,
        ]
        self.logger.info(
            "ffmpeg-pipe backend: binary=%s codec=%s", binary, self.config.ffmpeg_codec
        )
        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, args=(self._proc,), daemon=True
        )
        self._stderr_thread.start()
        self._reader = threading.Thread(
            target=self._read_frames, args=(self._proc,), daemon=True
        )
        self._reader.start()
        return self._proc

    def _drain_stderr(self, proc: subprocess.Popen) -> None:
        try:
            for line in iter(proc.stderr.readline, b""):
                text = line.decode("utf-8", "replace").strip()
                if getattr(self, "_raw_mode", False) and "rawvideo" in text:
                    import re as _re
                    _m = _re.search(r"(\d{2,5})x(\d{2,5})", text)
                    if _m:
                        self._raw_dims = (int(_m.group(1)), int(_m.group(2)))
                        self._raw_dims_ready.set()
                if text:
                    self.logger.warning("ffmpeg: %s", text)
        except Exception:
            pass

    def _read_frames(self, proc: subprocess.Popen) -> None:
        if getattr(self, "_raw_mode", False):
            self._read_frames_raw(proc)
            return
        import av
        import cv2
        import numpy as np
        try:
            with av.open(proc.stdout, format="nut") as container:
                _prev_end = None
                for frame in container.decode(video=0):
                    _t0 = time.monotonic()
                    if self._timing and _prev_end is not None:
                        self._t_wait.append(_t0 - _prev_end)
                    self._write_display(frame, np)
                    _t1 = time.monotonic()
                    image = self._frame_to_bgr(frame, cv2, np) if self.config.convert_bgr else None
                    _t2 = time.monotonic()
                    now = time.monotonic()
                    au = self._au_context
                    received_at = au.received_at if au is not None else now
                    self.sequence += 1
                    item = Frame(
                        image=image,
                        sequence=self.sequence,
                        width=int(frame.width),
                        height=int(frame.height),
                        received_at=received_at,
                        decoded_at=now,
                        pts=float(frame.time) if frame.time is not None else None,
                        keyframe=bool(frame.key_frame),
                        au_index=self._au_index,
                        latency_s=max(0.0, now - received_at),
                        corrupt=bool(getattr(frame, "is_corrupt", False)),
                    )
                    try:
                        self._frame_q.put_nowait(item)
                    except queue.Full:
                        try:
                            self._frame_q.get_nowait()
                        except queue.Empty:
                            pass
                        self._pipe_dropped += 1
                        self._frame_q.put_nowait(item)
                    _prev_end = time.monotonic()
                    if self._timing:
                        self._t_disp.append(_t1 - _t0)
                        self._t_bgr.append(_t2 - _t1)
                        self._t_build.append(_prev_end - _t2)
                        self._maybe_log_timing()
        except Exception as exc:
            if not self._terminated:
                self._reader_error = repr(exc)
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass


    def _maybe_log_timing(self) -> None:
        now = time.monotonic()
        if now - self._t_log_at < 5.0:
            return
        self._t_log_at = now

        def q(values, p):
            if not values:
                return 0.0
            ordered = sorted(values)
            idx = max(0, min(len(ordered) - 1, int(round(p * (len(ordered) - 1)))))
            return ordered[idx] * 1000.0

        for name, values in (
            ("wait", self._t_wait),
            ("display", self._t_disp),
            ("bgr", self._t_bgr),
            ("build", self._t_build),
        ):
            if values:
                self.logger.warning(
                    "pipe timing %s n=%d p50=%.1fms p95=%.1fms max=%.1fms",
                    name, len(values), q(values, 0.50), q(values, 0.95), q(values, 1.0),
                )
        for values in (self._t_wait, self._t_disp, self._t_bgr, self._t_build):
            values.clear()


    def _read_exact(self, stream: Any, size: int) -> bytes:
        chunks = []
        remaining = size
        while remaining > 0 and not self._terminated:
            data = stream.read(remaining)
            if not data:
                break
            chunks.append(data)
            remaining -= len(data)
        return b"".join(chunks)

    def _write_display_raw(self, arr: Any) -> None:
        if self.config.display != "ffplay" or self._display_disabled:
            return
        if self._display_min_interval > 0:
            now = time.monotonic()
            if now - self._display_last_at < self._display_min_interval:
                return
            self._display_last_at = now
        green = self._looks_like_green_curtain(arr)
        partial_green = (not green) and self._looks_like_partial_green(arr)
        if green or partial_green:
            if partial_green:
                self._display_partial_green_dropped += 1
            self._display_green_dropped += 1
            return
        if self._looks_like_grey_frame(arr):
            self._display_grey_dropped += 1
            return
        self._ensure_display(int(arr.shape[1]), int(arr.shape[0] * 2 // 3))
        q = self._display_q
        if q is None:
            return
        try:
            q.put_nowait(arr)
        except queue.Full:
            self._display_dropped += 1
            try:
                q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(arr)
            except queue.Full:
                pass

    def _read_frames_raw(self, proc: subprocess.Popen) -> None:
        import cv2
        import numpy as np
        try:
            if not self._raw_dims_ready.wait(20.0):
                raise RuntimeError("raw transport: no frame size from ffmpeg stderr")
            w, h = self._raw_dims
            size = w * h * 3 // 2
            stream = proc.stdout
            while not self._terminated:
                data = self._read_exact(stream, size)
                if len(data) != size:
                    break
                arr = np.frombuffer(data, dtype=np.uint8).reshape(h + h // 2, w)
                self._write_display_raw(arr)
                image = cv2.cvtColor(arr, cv2.COLOR_YUV2BGR_NV12) if self.config.convert_bgr else None
                now = time.monotonic()
                au = self._au_context
                received_at = au.received_at if au is not None else now
                self.sequence += 1
                item = Frame(
                    image=image,
                    sequence=self.sequence,
                    width=w,
                    height=h,
                    received_at=received_at,
                    decoded_at=now,
                    pts=None,
                    keyframe=bool(au.has_irap) if au is not None else False,
                    au_index=self._au_index,
                    latency_s=max(0.0, now - received_at),
                    corrupt=False,
                )
                try:
                    self._frame_q.put_nowait(item)
                except queue.Full:
                    try:
                        self._frame_q.get_nowait()
                    except queue.Empty:
                        pass
                    self._pipe_dropped += 1
                    self._frame_q.put_nowait(item)
        except Exception as exc:
            if not self._terminated:
                self._reader_error = repr(exc)
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

    @staticmethod
    def _pack_nv12(frame: Any, np: Any) -> Any:
        h, w = frame.height, frame.width
        p0, p1 = frame.planes[0], frame.planes[1]
        y = np.frombuffer(p0, dtype=np.uint8)[: h * p0.line_size].reshape(h, p0.line_size)[:, :w]
        uv = np.frombuffer(p1, dtype=np.uint8)[: (h // 2) * p1.line_size].reshape(h // 2, p1.line_size)[:, :w]
        buf = np.empty((h + h // 2, w), dtype=np.uint8)
        buf[:h] = y
        buf[h:] = uv
        return buf

    @staticmethod
    def _frame_to_bgr(frame: Any, cv2: Any, np: Any) -> Any:
        if frame.format.name == "nv12":
            return cv2.cvtColor(FfmpegPipeDecoder._pack_nv12(frame, np), cv2.COLOR_YUV2BGR_NV12)
        return frame.to_ndarray(format="bgr24")

    def _close_display(self) -> None:
        proc = self._display_proc
        self._display_proc = None
        self._display_dims = None
        self._display_stop.set()
        self._display_q = None
        if proc is None:
            self._display_writer = None
            return
        try:
            proc.stdin.close()
        except Exception:
            pass
        writer = self._display_writer
        self._display_writer = None
        if writer is not None:
            writer.join(timeout=2.0)
        try:
            proc.wait(timeout=5.0)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self.logger.info("ffplay display closed")

    def _display_loop(self, proc: subprocess.Popen) -> None:
        while not self._display_stop.is_set():
            q = self._display_q
            if q is None:
                return
            try:
                buf = q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                proc.stdin.write(buf.tobytes())
                proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as exc:
                if not self._display_stop.is_set():
                    self.logger.warning(
                        "ffplay display write failed (%r); display disabled", exc
                    )
                    self._display_disabled = True
                    self._close_display()
                return

    @staticmethod
    def _looks_like_green_curtain(packed: Any) -> bool:
        h = packed.shape[0] * 2 // 3
        y = packed[:h]
        uv = packed[h:]
        # A zeroed NV12 plane set renders as a green curtain (Y=0, U=V=0).
        return float(y[::16, ::16].mean()) < 4.0 and float(uv[::16, ::16].mean()) < 4.0

    @staticmethod
    def _looks_like_partial_green(packed: Any) -> bool:
        h = packed.shape[0] * 2 // 3
        y = packed[:h][::8, ::8]
        uv = packed[h:][::8, ::8]
        # Synthetic green (zeroed Y and UV) in a large region, e.g. a
        # partially written frame after a decoder abort. The planes have
        # different sizes, so evaluate them separately.
        y_green = float((y < 4).mean())
        uv_green = float((uv < 4).mean())
        return y_green > 0.2 and uv_green > 0.2

    @staticmethod
    def _looks_like_grey_frame(packed: Any) -> bool:
        h = packed.shape[0] * 2 // 3
        y = packed[:h][::16, ::16]
        uv = packed[h:][::16, ::16]
        # Software HEVC concealment fills a missing picture with uniform grey.
        return (
            abs(float(y.mean()) - 128.0) <= 4.0
            and float(y.std()) <= 2.5
            and abs(float(uv.mean()) - 128.0) <= 4.0
            and float(uv.std()) <= 2.5
        )

    def _ensure_display(self, w: int, h: int) -> None:
        if self.config.display not in ("ffplay", "kms") or self._display_disabled:
            return
        if self._display_proc is not None:
            if self._display_dims == (w, h):
                if self._display_proc.poll() is None:
                    return
            self._close_display()
        if self.config.display == "kms":
            binary = os.environ.get("VT13_KMS_RENDER") or os.path.expanduser(
                "~/mobile_vt/.codex_tmp/kiosk_20261110/kms_render")
            if not os.path.exists(binary):
                self.logger.warning("kms display requested but %s missing; display disabled", binary)
                self._display_disabled = True
                return
            cmd = [binary, "--stdin", "--dumb", "--hide-primary", "--video", f"{w}x{h}"]
        else:
            binary = self.config.ffplay_path or shutil.which("ffplay")
            if not binary:
                self.logger.warning("ffplay display requested but no ffplay binary; display disabled")
                self._display_disabled = True
                return
            cmd = [binary, "-hide_banner", "-loglevel", "warning", "-autoexit",
                   "-fflags", "nobuffer", "-flags", "low_delay", "-framedrop",
                   "-probesize", "32", "-analyzeduration", "0", "-an", "-sn",
                   "-f", "rawvideo", "-pixel_format", "nv12", "-video_size", f"{w}x{h}",
                   "-framerate", "60", "-x", str(self.config.display_width),
                   "-y", str(self.config.display_height), "-window_title", "VT13-Video",
                   "-i", "pipe:0"]
        self._display_proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self._display_dims = (w, h)
        self._display_q = queue.Queue(maxsize=1)
        self._display_stop.clear()
        self._display_writer = threading.Thread(
            target=self._display_loop, args=(self._display_proc,), daemon=True
        )
        self._display_writer.start()
        self.logger.info("%s display started: %dx%d", self.config.display, w, h)

    def _write_display(self, frame: Any, np: Any) -> None:
        if self.config.display not in ("ffplay", "kms") or self._display_disabled:
            return
        if frame.format.name != "nv12":
            return
        if bool(getattr(frame, "is_corrupt", False)):
            self._display_corrupt_dropped += 1
            return
        if self._display_min_interval > 0:
            _now = time.monotonic()
            if _now - self._display_last_at < self._display_min_interval:
                return
            self._display_last_at = _now
        packed = self._pack_nv12(frame, np)
        green = self._looks_like_green_curtain(packed)
        partial_green = (not green) and self._looks_like_partial_green(packed)
        if green or partial_green:
            if partial_green:
                self._display_partial_green_dropped += 1
            self._display_green_dropped += 1
            return
        if self._looks_like_grey_frame(packed):
            self._display_grey_dropped += 1
            return
        self._ensure_display(int(frame.width), int(frame.height))
        q = self._display_q
        if q is None:
            return
        try:
            q.put_nowait(packed)
        except queue.Full:
            self._display_dropped += 1
            try:
                q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(packed)
            except queue.Full:
                pass

    def _restart_for_sps_change(self) -> list[Frame]:
        # The CLI raw-hevc demuxer sets extradata, and the decoder then ignores
        # mid-stream SPS updates with the same id; a fresh process initializes
        # from the new in-band parameter sets instead.
        self.logger.info("ffmpeg-pipe: SPS changed; restarting ffmpeg for new resolution")
        proc = self._proc
        old_frames: list[Frame] = []
        if proc is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
            if self._reader is not None:
                self._reader.join(timeout=5.0)
                if self._reader.is_alive():
                    self.logger.warning("ffmpeg-pipe: old process drain exceeded 5s; terminating")
            while True:
                try:
                    old_frames.append(self._frame_q.get_nowait())
                except queue.Empty:
                    break
            self._terminate(keep_display=True)
        self._ctx = self._new_context()
        return old_frames

    def _decode_bytes(self, data: bytes, au: AccessUnit) -> list[Frame]:
        self._au_context = au
        frames: list[Frame] = []
        for nal in scan_nals(data):
            if nal.nal_type == 33:
                digest = hashlib.sha256(nal.payload).digest()
                if self._last_sps_hash is not None and digest != self._last_sps_hash:
                    frames.extend(self._restart_for_sps_change())
                self._last_sps_hash = digest
        proc = self._proc
        if proc is None or proc.poll() is not None:
            if proc is not None:
                self._terminate(keep_display=True)
            self._ctx = self._new_context()
            proc = self._proc
        try:
            proc.stdin.write(data)
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._record_error(exc)
            self._maybe_reset_after_errors()
            return []
        if self._reader_error:
            err = self._reader_error
            self._reader_error = None
            self._record_error(RuntimeError(err))
        while True:
            try:
                frames.append(self._frame_q.get_nowait())
            except queue.Empty:
                break
        self.consecutive_errors = 0 if frames else self.consecutive_errors
        self._maybe_reset_after_errors()
        self.frames_decoded += len(frames)
        return frames

    def _terminate(self, keep_display: bool = False) -> None:
        self._terminated = True
        if not keep_display:
            self._close_display()
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        if self._reader is not None:
            self._reader.join(timeout=5.0)
        try:
            proc.wait(timeout=5.0)
        except Exception:
            pass
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream is not None and not stream.closed:
                    stream.close()
            except Exception:
                pass
        self._proc = None

    def reset(self) -> None:
        # Keep the HDMI window alive across a decoder reset and defer the next
        # ffmpeg spawn until a usable IRAP arrives.
        self._terminate(keep_display=True)
        self._reader_error = None
        self._ctx = None
        self.needs_keyframe = True
        self.consecutive_errors = 0
        self.waiting_reason = None
        self.resets += 1

    def flush(self) -> list[Frame]:
        proc = self._proc
        if proc is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
            if self._reader is not None:
                self._reader.join(timeout=10.0)
                if self._reader.is_alive():
                    self.logger.warning(
                        "ffmpeg-pipe EOF drain exceeded 10s; terminating (known v4l2m2m drain issue)"
                    )
                    self._terminate()
        frames: list[Frame] = []
        while True:
            try:
                frames.append(self._frame_q.get_nowait())
            except queue.Empty:
                break
        self._close_display()
        self.frames_decoded += len(frames)
        return frames

    def snapshot(self) -> dict[str, Any]:
        snap = super().snapshot()
        snap["backend"] = "ffmpeg-pipe"
        snap["ffmpeg_codec"] = self.config.ffmpeg_codec
        snap["pipe_dropped"] = self._pipe_dropped
        snap["display"] = (
            "disabled" if self._display_disabled
            else ("ffplay" if self._display_proc is not None else self.config.display)
        )
        snap["display_dropped"] = self._display_dropped
        snap["display_corrupt_dropped"] = self._display_corrupt_dropped
        snap["display_green_dropped"] = self._display_green_dropped
        snap["display_grey_dropped"] = self._display_grey_dropped
        snap["display_partial_green_dropped"] = self._display_partial_green_dropped
        proc = self._proc
        snap["ffmpeg_alive"] = bool(proc is not None and proc.poll() is None)
        return snap