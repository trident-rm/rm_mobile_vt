"""Thread-safe runtime statistics for the VT13 video pipeline."""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import threading
import time
from typing import Any

from .decoder import Frame
from .nal import AccessUnit, NAL_NAMES, NALUnit


def _human_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / (1024 * 1024):.2f} MiB"


@dataclass
class StreamStats:
    started_at: float | None = None
    state: str = "starting"
    state_detail: str | None = None
    device_identity: str | None = None

    usb_bytes: int = 0
    usb_reads: int = 0
    usb_timeouts: int = 0
    usb_empty_reads: int = 0
    usb_errors: int = 0
    usb_recoveries: int = 0
    usb_resets: int = 0
    usb_halt_clears: int = 0
    usb_halt_clear_failures: int = 0
    record_bytes: int = 0
    last_error: str | None = None
    last_error_kind: str | None = None
    last_error_at: float | None = None
    last_error_errno: int | None = None
    last_error_backend_code: int | None = None
    last_error_reads: int | None = None
    last_error_bytes: int | None = None
    last_error_since_data_s: float | None = None
    last_data_at: float | None = None

    nals: int = 0
    nals_by_type: Counter = field(default_factory=Counter)
    auds: int = 0
    vcl: int = 0
    irap: int = 0
    parameter_sets: Counter = field(default_factory=Counter)

    aus: int = 0
    irap_aus: int = 0
    skipped_aus: int = 0
    keyframe_starts: int = 0
    discontinuities: int = 0
    last_discontinuity: str | None = None

    decoded_frames: int = 0
    decode_errors: int = 0
    decoder_resets: int = 0
    dropped_frames: int = 0
    last_frame_at: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    fps: float = 0.0
    _frame_times: deque[float] = field(default_factory=lambda: deque(maxlen=240))

    _lock: Any = field(default_factory=threading.Lock, repr=False)

    def start(self, now: float | None = None) -> None:
        with self._lock:
            self.started_at = time.monotonic() if now is None else now
            self.state = "starting"
            self.state_detail = None

    def set_state(self, state: str, detail: str | None = None) -> None:
        with self._lock:
            self.state = state
            self.state_detail = detail

    def record_read(self, nbytes: int, now: float) -> None:
        with self._lock:
            self.usb_bytes += nbytes
            self.usb_reads += 1
            self.last_data_at = now

    def record_timeout(self) -> None:
        with self._lock:
            self.usb_timeouts += 1

    def record_empty_read(self) -> None:
        with self._lock:
            self.usb_empty_reads += 1

    def read_context(self) -> dict[str, int]:
        with self._lock:
            return {
                "reads": self.usb_reads,
                "bytes": self.usb_bytes,
                "timeouts": self.usb_timeouts,
                "empty_reads": self.usb_empty_reads,
            }

    def record_error(
        self,
        kind: str,
        message: str,
        now: float | None = None,
        *,
        errno: int | None = None,
        backend_error_code: int | None = None,
        reads: int | None = None,
        bytes_read: int | None = None,
        since_data_s: float | None = None,
    ) -> None:
        with self._lock:
            self.usb_errors += 1
            self.last_error_kind = kind
            self.last_error = message
            self.last_error_at = time.monotonic() if now is None else now
            self.last_error_errno = errno
            self.last_error_backend_code = backend_error_code
            self.last_error_reads = reads
            self.last_error_bytes = bytes_read
            self.last_error_since_data_s = since_data_s

    def record_recovery(self, reason: str | None = None) -> None:
        with self._lock:
            self.usb_recoveries += 1
            if reason:
                self.last_discontinuity = reason

    def record_reset(self) -> None:
        with self._lock:
            self.usb_resets += 1

    def record_halt_clear(self, ok: bool) -> None:
        with self._lock:
            self.usb_halt_clears += 1
            if not ok:
                self.usb_halt_clear_failures += 1

    def record_discontinuity(self, reason: str) -> None:
        with self._lock:
            self.discontinuities += 1
            self.last_discontinuity = reason

    def record_nal(self, nal: NALUnit) -> None:
        with self._lock:
            self.nals += 1
            self.nals_by_type[nal.nal_type] += 1
            if nal.is_aud:
                self.auds += 1
            if nal.is_vcl:
                self.vcl += 1
            if nal.is_irap:
                self.irap += 1
            if nal.is_parameter_set:
                self.parameter_sets[nal.nal_type] += 1

    def record_au(self, au: AccessUnit) -> None:
        with self._lock:
            self.aus += 1
            if au.has_irap:
                self.irap_aus += 1

    def record_skipped_au(self) -> None:
        with self._lock:
            self.skipped_aus += 1

    def record_keyframe_start(self) -> None:
        with self._lock:
            self.keyframe_starts += 1

    def record_frame(self, frame: Frame) -> None:
        with self._lock:
            self.decoded_frames += 1
            self.last_frame_at = frame.decoded_at
            self.frame_width = frame.width
            self.frame_height = frame.height
            self._frame_times.append(frame.decoded_at)
            self._update_fps(frame.decoded_at)

    def record_decode_error(self, count: int = 1) -> None:
        with self._lock:
            self.decode_errors += count

    def record_decoder_reset(self) -> None:
        with self._lock:
            self.decoder_resets += 1

    def record_recorded_bytes(self, count: int) -> None:
        with self._lock:
            self.record_bytes += count

    def _update_fps(self, now: float) -> None:
        cutoff = now - 2.0
        while self._frame_times and self._frame_times[0] < cutoff:
            self._frame_times.popleft()
        if len(self._frame_times) < 2:
            self.fps = 0.0
            return
        span = self._frame_times[-1] - self._frame_times[0]
        self.fps = (len(self._frame_times) - 1) / span if span > 0 else 0.0

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        now = time.monotonic() if now is None else now
        with self._lock:
            elapsed = 0.0 if self.started_at is None else max(0.0, now - self.started_at)
            seconds_since_data = (
                None if self.last_data_at is None else max(0.0, now - self.last_data_at)
            )
            seconds_since_frame = (
                None if self.last_frame_at is None else max(0.0, now - self.last_frame_at)
            )
            return {
                "state": self.state,
                "state_detail": self.state_detail,
                "device": self.device_identity,
                "elapsed_s": round(elapsed, 3),
                "usb": {
                    "bytes": self.usb_bytes,
                    "bytes_human": _human_bytes(self.usb_bytes),
                    "reads": self.usb_reads,
                    "timeouts": self.usb_timeouts,
                    "empty_reads": self.usb_empty_reads,
                    "errors": self.usb_errors,
                    "recoveries": self.usb_recoveries,
                    "resets": self.usb_resets,
                    "halt_clears": self.usb_halt_clears,
                    "halt_clear_failures": self.usb_halt_clear_failures,
                    "last_error": self.last_error,
                    "last_error_kind": self.last_error_kind,
                    "last_error_at": self.last_error_at,
                    "last_error_errno": self.last_error_errno,
                    "last_error_backend_code": self.last_error_backend_code,
                    "last_error_reads": self.last_error_reads,
                    "last_error_bytes": self.last_error_bytes,
                    "last_error_since_data_s": self.last_error_since_data_s,
                    "seconds_since_data": (
                        None if seconds_since_data is None else round(seconds_since_data, 3)
                    ),
                },
                "stream": {
                    "nals": self.nals,
                    "nals_by_type": {
                        NAL_NAMES.get(t, str(t)): c
                        for t, c in sorted(self.nals_by_type.items())
                    },
                    "auds": self.auds,
                    "vcl": self.vcl,
                    "irap": self.irap,
                    "parameter_sets": {
                        NAL_NAMES.get(t, str(t)): c for t, c in sorted(self.parameter_sets.items())
                    },
                    "access_units": self.aus,
                    "irap_access_units": self.irap_aus,
                    "skipped_access_units": self.skipped_aus,
                    "keyframe_starts": self.keyframe_starts,
                    "discontinuities": self.discontinuities,
                    "last_discontinuity": self.last_discontinuity,
                },
                "decode": {
                    "frames": self.decoded_frames,
                    "fps": round(self.fps, 2),
                    "width": self.frame_width,
                    "height": self.frame_height,
                    "errors": self.decode_errors,
                    "resets": self.decoder_resets,
                    "dropped_frames": self.dropped_frames,
                    "seconds_since_frame": (
                        None if seconds_since_frame is None else round(seconds_since_frame, 3)
                    ),
                },
                "recording": {"bytes": self.record_bytes},
            }

    def status_line(self) -> str:
        with self._lock:
            fps = self.fps
            frames = self.decoded_frames
            errors = self.usb_errors + self.decode_errors
            return (
                f"{self.state}: {_human_bytes(self.usb_bytes)} USB, "
                f"{frames} frames, {fps:.1f} FPS, {errors} errors, "
                f"{self.usb_recoveries} recoveries"
            )
