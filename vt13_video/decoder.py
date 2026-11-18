"""PyAV HEVC decoder with keyframe-gated startup and frame queue."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import queue
import threading
import time
from typing import Any

from .config import DecoderConfig
from .nal import AccessUnit


class DependencyError(RuntimeError):
    """Raised when an optional runtime dependency is unavailable."""


@dataclass(frozen=True)
class Frame:
    image: Any
    sequence: int
    width: int
    height: int
    received_at: float
    decoded_at: float
    pts: float | None
    keyframe: bool
    au_index: int
    latency_s: float
    corrupt: bool = False

class FrameQueue:
    """Bounded frame queue that prefers fresh frames over backlog."""

    def __init__(self, maxsize: int = 8, drop_oldest: bool = True) -> None:
        self._queue: queue.Queue[Frame] = queue.Queue(maxsize=maxsize)
        self.drop_oldest = drop_oldest
        self._latest: Frame | None = None
        self._lock = threading.Lock()
        self.dropped = 0

    def put(self, frame: Frame) -> None:
        if self.drop_oldest:
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                self.dropped += 1
                self._queue.put_nowait(frame)
        else:
            self._queue.put(frame)
        with self._lock:
            self._latest = frame

    def get(self, timeout: float | None = None) -> Frame | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def latest(self) -> Frame | None:
        with self._lock:
            return self._latest

    def qsize(self) -> int:
        return self._queue.qsize()


class HevcDecoder:
    """Decode complete access units, starting only at a usable IRAP."""

    def __init__(self, config: DecoderConfig, logger: logging.Logger | None = None) -> None:
        try:
            import av
        except ImportError as exc:
            raise DependencyError("PyAV is required for decoding; install the 'av' package") from exc
        self.av = av
        self.config = config
        self.logger = logger or logging.getLogger("vt13_video.decoder")
        self._ctx = self._new_context()
        self.needs_keyframe = config.require_keyframe
        self.waiting_reason: str | None = None
        self.errors = 0
        self.consecutive_errors = 0
        self.resets = 0
        self.frames_decoded = 0
        self.corrupt_frames = 0
        self.sequence = 0
        self._au_index = 0

    def _new_context(self):
        ctx = self.av.CodecContext.create(self.config.codec, "r")
        # BEGIN VT13_AV_THREADS_EXPERIMENT
        import os as _vt13_os
        _vt13_n = int(_vt13_os.environ.get("VT13_AV_THREADS", "0"))
        if _vt13_n > 0:
            _vt13_thread_type = _vt13_os.environ.get("VT13_AV_THREAD_TYPE", "AUTO").upper()
            if _vt13_thread_type not in {"AUTO", "FRAME", "SLICE"}:
                raise ValueError("VT13_AV_THREAD_TYPE must be AUTO, FRAME, or SLICE")
            ctx.thread_type = _vt13_thread_type
            ctx.thread_count = _vt13_n
            self.logger.info("experimental PyAV threads: %d", _vt13_n)
        # END VT13_AV_THREADS_EXPERIMENT
        if self.config.allow_corrupt_frames:
            flag = getattr(self.av.codec.context.Flags, "output_corrupt", 1 << 3)
            ctx.flags |= int(flag)
        self.logger.info(
            "HEVC decoder context created: requested=%s actual=%s",
            self.config.codec,
            ctx.codec.name,
        )
        return ctx

    def reset(self) -> None:
        self._ctx = self._new_context()
        self.needs_keyframe = True
        self.consecutive_errors = 0
        self.waiting_reason = None
        self.resets += 1

    def decode(self, au: AccessUnit, bootstrap_bytes: bytes = b"") -> list[Frame]:
        self._au_index += 1
        if self.needs_keyframe:
            if not au.has_irap:
                self.waiting_reason = "waiting for VPS/SPS/PPS + IRAP"
                return []
            if not au.has_all_parameter_sets and not bootstrap_bytes:
                self.waiting_reason = "IRAP seen but parameter sets are missing"
                return []
            data = bootstrap_bytes + au.wire_bytes
            self.needs_keyframe = False
            self.waiting_reason = None
        else:
            if not au.has_vcl:
                return []
            data = au.wire_bytes
        return self._decode_bytes(data, au)

    def _decode_bytes(self, data: bytes, au: AccessUnit) -> list[Frame]:
        try:
            packets = self._ctx.parse(data)
        except self.av.error.FFmpegError as exc:
            self._record_error(exc)
            self._maybe_reset_after_errors()
            return []

        frames: list[Frame] = []
        for packet in packets:
            try:
                decoded = self._ctx.decode(packet)
            except self.av.error.FFmpegError as exc:
                self._record_error(exc)
                continue
            self.consecutive_errors = 0
            self.waiting_reason = None
            frames.extend(self._collect_frames(decoded, au))

        self._maybe_reset_after_errors()
        self.frames_decoded += len(frames)
        return frames

    def _maybe_reset_after_errors(self) -> None:
        if self.consecutive_errors >= self.config.max_consecutive_errors:
            self.logger.warning(
                "decoder hit %d consecutive errors; resetting and waiting for the next IRAP",
                self.consecutive_errors,
            )
            self.reset()
            self.waiting_reason = "decoder reset after consecutive errors"

    def _collect_frames(self, decoded: Any, au: AccessUnit | None) -> list[Frame]:
        frames: list[Frame] = []
        for av_frame in decoded:
            corrupt = bool(getattr(av_frame, "is_corrupt", False))
            if corrupt:
                self.corrupt_frames += 1
                if not self.config.emit_corrupt_frames:
                    continue
            frames.append(self._convert_frame(av_frame, au, corrupt=corrupt))
        return frames

    def _convert_frame(
        self, av_frame: Any, au: AccessUnit | None, *, corrupt: bool | None = None
    ) -> Frame:
        image = av_frame.to_ndarray(format=self.config.output_format)
        now = time.monotonic()
        received_at = au.received_at if au is not None else now
        keyframe = bool(au is not None and au.has_irap)
        pts = float(av_frame.time) if av_frame.time is not None else None
        if corrupt is None:
            corrupt = bool(getattr(av_frame, "is_corrupt", False))
        self.sequence += 1
        return Frame(
            image=image,
            sequence=self.sequence,
            width=int(av_frame.width),
            height=int(av_frame.height),
            received_at=received_at,
            decoded_at=now,
            pts=pts,
            keyframe=keyframe,
            au_index=self._au_index,
            latency_s=max(0.0, now - received_at),
            corrupt=corrupt,
        )

    def _record_error(self, exc: BaseException) -> None:
        self.errors += 1
        self.consecutive_errors += 1
        if self.errors <= 5:
            self.logger.warning("HEVC decode error: %s", exc)

    def flush(self) -> list[Frame]:
        """Flush buffered decoder frames at end of stream."""
        frames: list[Frame] = []
        try:
            packets = self._ctx.parse(b"")
        except Exception as exc:
            self.logger.debug("decoder flush parse failed: %r", exc)
            packets = []
        for packet in packets:
            try:
                decoded = self._ctx.decode(packet)
            except Exception as exc:
                self.logger.debug("decoder flush packet failed: %r", exc)
                continue
            frames.extend(self._collect_frames(decoded, None))
        try:
            decoded = self._ctx.decode(None)
        except Exception as exc:
            self.logger.debug("decoder flush drain failed: %r", exc)
            decoded = []
        frames.extend(self._collect_frames(decoded, None))
        self.frames_decoded += len(frames)
        return frames

    def snapshot(self) -> dict[str, Any]:
        return {
            "codec": self.config.codec,
            "needs_keyframe": self.needs_keyframe,
            "waiting_reason": self.waiting_reason,
            "errors": self.errors,
            "consecutive_errors": self.consecutive_errors,
            "resets": self.resets,
            "frames_decoded": self.frames_decoded,
            "corrupt_frames": self.corrupt_frames,
            "au_index": self._au_index,
        }
