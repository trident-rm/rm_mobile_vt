"""Byte sources for live USB reads and offline replay."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import logging
import threading
import time
from typing import Protocol

from .config import DeviceConfig, ReadConfig
from .device import DeviceAccessError, DeviceError, find_device


class SourceError(RuntimeError):
    kind = "unknown"


class UsbReadError(SourceError):
    def __init__(
        self,
        message: str,
        *,
        kind: str = "unknown",
        errno: int | None = None,
        backend_error_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.errno = errno
        self.backend_error_code = backend_error_code


class ReadTimeout(UsbReadError):
    def __init__(self, message: str = "USB read timed out", **kwargs) -> None:
        super().__init__(message, kind="timeout", **kwargs)


@dataclass(frozen=True)
class ReadResult:
    data: bytes
    received_at: float
    source_gap_s: float | None = None
    eof: bool = False


class ByteSource(Protocol):
    @property
    def identity(self) -> str: ...

    def open(self) -> None: ...

    def read(self) -> ReadResult: ...

    def close(self) -> None: ...

    def drain(self, count: int) -> bytes: ...

    def clear_halt(self) -> bool: ...

    def reset_device(self) -> bool: ...


def classify_usb_error(exc: BaseException) -> str:
    errno = getattr(exc, "errno", None)
    backend = getattr(exc, "backend_error_code", None)
    text = str(exc).lower()
    if errno == 110 or backend == -7 or "timed out" in text or "timeout" in text:
        return "timeout"
    if errno == 19 or backend == -4 or "no such device" in text or "disconnected" in text:
        return "disconnected"
    if errno == 13 or backend == -3 or "access" in text or "permission" in text:
        return "access"
    if errno == 32 or backend == -9 or "pipe" in text or "stall" in text:
        return "pipe"
    if errno == 75 or backend == -8 or "overflow" in text:
        return "overflow"
    if errno == 5 or backend == -1 or "input/output" in text or "i/o" in text:
        return "io"
    if errno == 16 or backend == -6 or "busy" in text:
        return "busy"
    if errno == 4 or backend == -10 or "interrupted" in text:
        return "interrupted"
    return "unknown"


def _wrap_usb_error(exc: BaseException) -> UsbReadError:
    kind = classify_usb_error(exc)
    errno = getattr(exc, "errno", None)
    backend = getattr(exc, "backend_error_code", None)
    message = f"{kind} USB read error: {exc}"
    if kind == "timeout":
        return ReadTimeout(message, errno=errno, backend_error_code=backend)
    return UsbReadError(message, kind=kind, errno=errno, backend_error_code=backend)


class VT13UsbSource:
    """Read-only Bulk IN source for the VT13 video endpoint."""

    def __init__(
        self,
        device: DeviceConfig,
        read: ReadConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self.device = device
        self.read_config = read
        self.logger = logger or logging.getLogger("vt13_video.source")
        self._dev = None
        self._claimed = False
        self._detached_kernel = False
        self._endpoint = device.endpoint
        self._status_endpoint = device.status_endpoint
        self._status_claimed = False
        self._status_stop = threading.Event()
        self._status_thread: threading.Thread | None = None
        self._status_lock = threading.Lock()
        self._status_bytes = 0
        self._status_reads = 0
        self._status_errors = 0
        self._status_halt_clears = 0
        self._identity = f"{device.vid:04x}:{device.pid:04x}"

    @property
    def identity(self) -> str:
        if self._dev is not None:
            try:
                return f"{self.device.vid:04x}:{self.device.pid:04x} bus {self._dev.bus} address {self._dev.address}"
            except Exception:
                pass
        return self._identity

    def open(self) -> None:
        import usb.util

        dev = find_device(self.device.vid, self.device.pid, self.device.serial)
        iface_number = self.device.interface
        endpoint = self.device.endpoint

        try:
            config = dev.get_active_configuration()
        except Exception as exc:
            raise DeviceAccessError(
                f"cannot read active USB configuration: {exc!r}. "
                "Check /dev/bus/usb permissions and install udev/99-vt13-video.rules."
            ) from exc

        interface = None
        for candidate in config:
            if int(candidate.bInterfaceNumber) == iface_number:
                interface = candidate
                break
        if interface is None:
            raise DeviceError(f"USB interface {iface_number} is not present")

        endpoints = tuple(int(ep.bEndpointAddress) for ep in interface)
        if endpoint not in endpoints:
            raise DeviceError(
                f"endpoint 0x{endpoint:02x} is not on interface {iface_number}; "
                f"available: {', '.join(f'0x{ep:02x}' for ep in endpoints) or 'none'}"
            )
        if not endpoint & 0x80:
            raise DeviceError(f"endpoint 0x{endpoint:02x} is not an IN endpoint")

        try:
            kernel_active = bool(dev.is_kernel_driver_active(iface_number))
        except (NotImplementedError, AttributeError):
            kernel_active = False
        except Exception as exc:
            self.logger.debug("kernel-driver check failed: %r", exc)
            kernel_active = False

        if kernel_active:
            if not self.device.detach_kernel_driver:
                raise DeviceError(
                    f"kernel driver owns USB interface {iface_number}; set "
                    "device.detach_kernel_driver=true only if you understand the trade-off"
                )
            try:
                dev.detach_kernel_driver(iface_number)
                self._detached_kernel = True
                self.logger.info("detached kernel driver from interface %d", iface_number)
            except Exception as exc:
                raise DeviceError(f"cannot detach kernel driver: {exc!r}") from exc

        try:
            usb.util.claim_interface(dev, iface_number)
            self._claimed = True
        except Exception as exc:
            if self._detached_kernel:
                try:
                    dev.attach_kernel_driver(iface_number)
                except Exception:
                    pass
                self._detached_kernel = False
            raise DeviceAccessError(
                f"cannot claim USB interface {iface_number}: {exc!r}. "
                "Check /dev/bus/usb permissions and install udev/99-vt13-video.rules."
            ) from exc

        self._dev = dev
        self._identity = self.identity
        self.logger.info("opened %s", self._identity)
        self._start_status_drain(config)

    def _start_status_drain(self, usb_config) -> None:
        if not self.device.status_drain:
            return
        iface_number = self.device.status_interface
        endpoint = self.device.status_endpoint
        if iface_number is None or endpoint is None:
            return

        import usb.util

        interface = None
        for candidate in usb_config:
            if int(candidate.bInterfaceNumber) == iface_number:
                interface = candidate
                break
        if interface is None:
            self.logger.warning(
                "status interface %d is not present; status drain disabled", iface_number
            )
            return

        endpoints = tuple(int(ep.bEndpointAddress) for ep in interface)
        if endpoint not in endpoints or not endpoint & 0x80:
            self.logger.warning(
                "status endpoint 0x%02x is not an IN endpoint on interface %d; "
                "status drain disabled",
                endpoint,
                iface_number,
            )
            return

        try:
            usb.util.claim_interface(self._dev, iface_number)
            self._status_claimed = True
        except Exception as exc:
            self.logger.warning(
                "cannot claim status interface %d for drain: %r; continuing without it",
                iface_number,
                exc,
            )
            return

        self._status_stop.clear()
        self._status_thread = threading.Thread(
            target=self._status_loop, name="vt13-status-drain", daemon=True
        )
        self._status_thread.start()
        self.logger.info(
            "draining status endpoint 0x%02x on interface %d", endpoint, iface_number
        )

    def _status_loop(self) -> None:
        while not self._status_stop.is_set():
            try:
                data = bytes(
                    self._dev.read(
                        self._status_endpoint,
                        self.read_config.read_size,
                        timeout=self.read_config.timeout_ms,
                    )
                )
            except Exception as exc:
                wrapped = _wrap_usb_error(exc)
                if wrapped.kind == "timeout":
                    continue
                with self._status_lock:
                    self._status_errors += 1
                    error_count = self._status_errors
                if error_count <= 3:
                    self.logger.warning(
                        "status endpoint read failure (%s): %s", wrapped.kind, wrapped
                    )
                if wrapped.kind in {"io", "pipe", "stall"}:
                    try:
                        self._dev.clear_halt(self._status_endpoint)
                        with self._status_lock:
                            self._status_halt_clears += 1
                    except Exception as halt_exc:
                        self.logger.debug(
                            "status endpoint clear_halt failed: %r", halt_exc
                        )
                continue

            with self._status_lock:
                self._status_reads += 1
                self._status_bytes += len(data)

    def status_snapshot(self) -> dict:
        with self._status_lock:
            return {
                "enabled": bool(self.device.status_drain),
                "interface": self.device.status_interface,
                "endpoint": self.device.status_endpoint,
                "claimed": self._status_claimed,
                "bytes": self._status_bytes,
                "reads": self._status_reads,
                "errors": self._status_errors,
                "halt_clears": self._status_halt_clears,
            }

    def read(self) -> ReadResult:
        if self._dev is None:
            raise SourceError("USB source is not open")
        try:
            data = bytes(
                self._dev.read(
                    self._endpoint,
                    self.read_config.read_size,
                    timeout=self.read_config.timeout_ms,
                )
            )
        except Exception as exc:
            raise _wrap_usb_error(exc) from exc
        return ReadResult(data=data, received_at=time.monotonic())

    def drain(self, count: int) -> bytes:
        """Read the first chunks after open without discarding their contents.

        The caller parses these bytes.  Discarding them can remove a fresh
        VPS/SPS/PPS or IRAP that arrived immediately after USB re-enumeration.
        """
        if self._dev is None or count <= 0:
            return b""
        chunks: list[bytes] = []
        for _ in range(count):
            try:
                data = bytes(self._dev.read(self._endpoint, self.read_config.read_size, timeout=1))
            except Exception:
                break
            if not data:
                break
            chunks.append(data)
        preroll = b"".join(chunks)
        if preroll:
            self.logger.debug("read %d pre-roll bytes after open", len(preroll))
        return preroll

    def clear_halt(self) -> bool:
        if self._dev is None:
            return False
        try:
            self._dev.clear_halt(self._endpoint)
            return True
        except Exception as exc:
            self.logger.warning("clear_halt failed: %r", exc)
            return False

    def reset_device(self) -> bool:
        if self._dev is None:
            return False
        try:
            self._dev.reset()
            self.logger.warning("USB device reset requested")
            return True
        except Exception as exc:
            self.logger.warning("USB reset failed: %r", exc)
            return False

    def close(self) -> None:
        import usb.util

        self._stop_status_drain()
        dev = self._dev
        if dev is None:
            self._status_claimed = False
            return
        if self._status_claimed:
            try:
                usb.util.release_interface(dev, self.device.status_interface)
            except Exception as exc:
                self.logger.debug("status release_interface failed: %r", exc)
            self._status_claimed = False
        if self._claimed:
            try:
                usb.util.release_interface(dev, self.device.interface)
            except Exception as exc:
                self.logger.debug("release_interface failed: %r", exc)
            self._claimed = False
        if self._detached_kernel:
            try:
                dev.attach_kernel_driver(self.device.interface)
            except Exception as exc:
                self.logger.debug("attach_kernel_driver failed: %r", exc)
            self._detached_kernel = False
        try:
            usb.util.dispose_resources(dev)
        except Exception as exc:
            self.logger.debug("dispose_resources failed: %r", exc)
        self._dev = None

    def _stop_status_drain(self) -> None:
        self._status_stop.set()
        thread = self._status_thread
        self._status_thread = None
        if thread is not None:
            timeout = max(1.0, self.read_config.timeout_ms / 1000.0 + 1.0)
            thread.join(timeout)


class FileSource:
    """Replay a raw capture, optionally using its USB read-timestamp file."""

    def __init__(
        self,
        path: Path | str,
        read_size: int = 16384,
        times_path: Path | str | None = None,
        realtime: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self.path = Path(path)
        self.read_size = read_size
        self.times_path = Path(times_path) if times_path is not None else None
        self.realtime = realtime
        self.logger = logger or logging.getLogger("vt13_video.replay")
        self._fh = None
        self._times: list[tuple[float, int]] | None = None
        self._index = 0
        self._previous_elapsed: float | None = None
        self._open_time: float | None = None

    @property
    def identity(self) -> str:
        return str(self.path)

    def _load_times(self) -> None:
        times_path = self.times_path
        if times_path is None:
            candidate = self.path.with_suffix(".times.tsv")
            if candidate.is_file():
                times_path = candidate
        if times_path is None or not times_path.is_file():
            self._times = None
            return
        rows: list[tuple[float, int]] = []
        total = 0
        try:
            for line in times_path.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.startswith("elapsed_s"):
                    continue
                fields = line.split("\t")
                if len(fields) < 2:
                    continue
                elapsed = float(fields[0])
                length = int(fields[1])
                rows.append((elapsed, length))
                total += length
        except (OSError, ValueError) as exc:
            self.logger.warning("cannot parse %s: %r; replaying with fixed read size", times_path, exc)
            self._times = None
            return
        if total != self.path.stat().st_size:
            self.logger.warning(
                "timestamp lengths (%d) do not match capture size (%d); "
                "replaying with fixed read size",
                total,
                self.path.stat().st_size,
            )
            self._times = None
            return
        self._times = rows

    def open(self) -> None:
        if not self.path.is_file():
            raise SourceError(f"capture file not found: {self.path}")
        self._fh = self.path.open("rb")
        self._index = 0
        self._previous_elapsed = None
        self._open_time = time.monotonic()
        self._load_times()

    def read(self) -> ReadResult:
        if self._fh is None:
            raise SourceError("file source is not open")
        now = time.monotonic()
        if self._times is None:
            data = self._fh.read(self.read_size)
            if not data:
                return ReadResult(b"", now, eof=True)
            return ReadResult(data, now)

        if self._index >= len(self._times):
            return ReadResult(b"", now, eof=True)
        elapsed, length = self._times[self._index]
        self._index += 1
        data = self._fh.read(length)
        if not data:
            return ReadResult(b"", now, eof=True)
        gap = None if self._previous_elapsed is None else max(0.0, elapsed - self._previous_elapsed)
        self._previous_elapsed = elapsed
        if self.realtime and self._open_time is not None:
            target = self._open_time + elapsed
            delay = target - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        return ReadResult(data, time.monotonic(), source_gap_s=gap)

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def drain(self, count: int) -> bytes:
        return b""

    def clear_halt(self) -> bool:
        return False

    def reset_device(self) -> bool:
        return False
