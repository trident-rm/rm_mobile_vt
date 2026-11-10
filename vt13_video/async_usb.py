"""Experimental bounded USB prefetcher for vt13_video.

One thread performs only source.read(); the existing pipeline thread keeps
all NAL parsing, HEVC decoding, queueing and display behavior. No raw bytes
are deliberately dropped. This is a diagnostic, not a real-time guarantee.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any

LOG = logging.getLogger("vt13_video.async_usb")


@dataclass
class _Failure:
    error: Exception


class AsyncBufferedSource:
    def __init__(self, source: Any, max_chunks: int = 16384, log_every_s: float = 3.0):
        if max_chunks < 16:
            raise ValueError("VT13_ASYNC_CHUNKS must be >=16")
        self._source = source
        self._max_chunks = max_chunks
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_chunks)
        self._stop = threading.Event()
        self._resume = threading.Event()
        self._thread: threading.Thread | None = None
        self._log_every_s = log_every_s
        self._rx_bytes = 0
        self._delivered_bytes = 0
        self._last_log = 0.0
        self._full_warn_at = 0.0

    def __getattr__(self, attr: str):
        # Expose source.identity, drain(), clear_halt(), reset_device(), etc.
        # Calls to these methods occur on the pipeline thread during recovery.
        return getattr(self._source, attr)

    def open(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("USB reader is still active at open()")
        self._source.open()
        self._queue = queue.Queue(maxsize=self._max_chunks)
        self._stop.clear()
        self._resume.clear()
        self._thread = None
        self._rx_bytes = 0
        self._delivered_bytes = 0
        self._last_log = time.monotonic()
        self._full_warn_at = 0.0

    def _start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._worker,
            name="vt13-usb-rx",
            daemon=True,
        )
        self._thread.start()
        LOG.info(
            "async USB reader active: queue capacity=%d chunks "
            "(about %.1f MiB at 2048 bytes/chunk)",
            self._max_chunks,
            self._max_chunks * 2048 / 1048576,
        )

    def read(self):
        self._start()
        # After an exception, the worker pauses until pipeline recovery has
        # completed and the pipeline asks for the next read.
        self._resume.set()
        try:
            item = self._queue.get(timeout=2.0)
        except queue.Empty:
            if self._thread is not None and not self._thread.is_alive():
                raise RuntimeError("async USB reader stopped unexpectedly")
            raise RuntimeError("async USB worker produced nothing for 2 seconds")
        if isinstance(item, _Failure):
            raise item.error
        self._delivered_bytes += len(item.data) if item.data else 0
        return item

    def _put(self, item) -> bool:
        while not self._stop.is_set():
            try:
                self._queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                now = time.monotonic()
                if now - self._full_warn_at > 3.0:
                    self._full_warn_at = now
                    LOG.warning(
                        "USB raw queue FULL (%d chunks / ~%.1f MiB backlog); "
                        "decoder cannot keep up; capture will eventually lag/loss",
                        self._queue.qsize(),
                        max(0, self._rx_bytes - self._delivered_bytes) / 1048576,
                    )
        return False

    def _worker(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    result = self._source.read()
                except Exception as error:
                    # Preserve ReadTimeout / SourceError object and semantics.
                    # Pause while pipeline performs clear_halt/reopen/reset,
                    # so it cannot race with another bulk read.
                    self._resume.clear()
                    if not self._put(_Failure(error)):
                        break
                    while not self._stop.is_set() and not self._resume.wait(0.1):
                        pass
                    continue
                if result.data:
                    self._rx_bytes += len(result.data)
                if not self._put(result):
                    break
                if result.eof:
                    break
                now = time.monotonic()
                if now - self._last_log >= self._log_every_s:
                    backlog = max(0, self._rx_bytes - self._delivered_bytes)
                    LOG.info(
                        "async USB: read=%.2f MiB, delivered=%.2f MiB, "
                        "backlog=%.2f MiB, queue=%d/%d chunks",
                        self._rx_bytes / 1048576,
                        self._delivered_bytes / 1048576,
                        backlog / 1048576,
                        self._queue.qsize(),
                        self._max_chunks,
                    )
                    self._last_log = now
        except Exception:
            LOG.exception("async USB worker crashed")
            # Signal an actionable exception on the pipeline thread.
            self._put(_Failure(RuntimeError("async USB worker crashed; see log")))

    def close(self) -> None:
        self._stop.set()
        self._resume.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            if self._thread.is_alive():
                # Do not close libusb while the read thread may still be active.
                raise RuntimeError("async USB worker did not stop within 3 seconds")
        self._thread = None
        self._source.close()
        LOG.info(
            "async USB session closed: received=%.2f MiB, delivered=%.2f MiB",
            self._rx_bytes / 1048576,
            self._delivered_bytes / 1048576,
        )
