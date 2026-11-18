"""DUML control channel for the VT13 receiver.

The receiver exposes a CDC-ACM control port (interface 2, usually
``/dev/ttyACM0``) next to the video endpoint.  The official client uses it to
ask the transmitter for an I-frame (command set 1 / id 1) and to poll the
pairing status once a second (9 / 85).  The video endpoint is independent of
this port, so the pipeline can keep reading EP 0x81 while a background thread
handles control traffic.

The encoder and decoder mirror ``rm-receiver-proto`` (reverse-engineered from
RoboMaster Client 12.0.0.213); the request frame is byte-for-byte identical to
the official client's.
"""
from __future__ import annotations

from dataclasses import dataclass
import glob
import logging
import os
from pathlib import Path
import select
import termios
import threading
import time
import tty
from typing import Any

from .config import ControlConfig

SOF = 0x55
DUML_OVERHEAD = 13
MAX_PAYLOAD = 0x3FF - DUML_OVERHEAD
SENDER_PC = 10 | (5 << 5)  # PC client 10/5, as the official client identifies itself
RECEIVER_LINK = 14
CRC8_INIT = 0x77
CRC16_INIT = 0x3692
CONTROL_INTERFACE = 2
USB_VID = 0x2CA3
USB_PID = 0x1020

_RECONNECT_INTERVAL_S = 1.0
_READ_TIMEOUT_S = 0.2
_MAX_CONTROL_BUFFER = 64 * 1024


def _build_crc8_table() -> list[int]:
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if crc & 1 else crc >> 1
        table.append(crc)
    return table


def _build_crc16_table() -> list[int]:
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
        table.append(crc)
    return table


_CRC8_TABLE = _build_crc8_table()
_CRC16_TABLE = _build_crc16_table()


def crc8(data: bytes, init: int = CRC8_INIT) -> int:
    crc = init
    for byte in data:
        crc = _CRC8_TABLE[(crc ^ byte) & 0xFF]
    return crc


def crc16(data: bytes, init: int = CRC16_INIT) -> int:
    crc = init
    for byte in data:
        crc = (crc >> 8) ^ _CRC16_TABLE[(crc ^ byte) & 0xFF]
    return crc


def encode_frame(
    cmd_set: int,
    cmd_id: int,
    payload: bytes,
    *,
    seq: int = 0,
    sender: int = SENDER_PC,
    receiver: int = RECEIVER_LINK,
    version: int = 1,
    ack_policy: int = 2,
) -> bytes:
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"DUML payload too long: {len(payload)} > {MAX_PAYLOAD}")
    total = DUML_OVERHEAD + len(payload)
    ver_len = total | (version << 10)
    out = bytearray(b"\x55")
    out += ver_len.to_bytes(2, "little")
    out.append(crc8(bytes(out)))
    out.append(sender)
    out.append(receiver)
    out += seq.to_bytes(2, "little")
    out.append((ack_policy & 0x03) << 5)
    out += bytes([cmd_set, cmd_id])
    out += payload
    out += crc16(bytes(out)).to_bytes(2, "little")
    return bytes(out)


def special_ctrl(liveview_reset: bool) -> bytes:
    flags = (1 << 2) | (int(liveview_reset) << 5)
    return bytes([0, 0, 0, 0, 0, flags, 0, 0, 0, flags])


def request_iframe_frame() -> bytes:
    return encode_frame(1, 1, special_ctrl(True))


def pairing_query_frame() -> bytes:
    return encode_frame(9, 85, b"\x00\x02")


@dataclass(frozen=True)
class DumlFrame:
    version: int
    sender: int
    sender_index: int
    receiver: int
    receiver_index: int
    seq: int
    is_ack: bool
    ack_policy: int
    cmd_set: int
    cmd_id: int
    payload: bytes

    @property
    def summary(self) -> str:
        direction = f"{self.sender}/{self.sender_index}->{self.receiver}/{self.receiver_index}"
        return (
            f"{self.cmd_set:02x}/{self.cmd_id:02x} {direction} "
            f"ack={self.is_ack} seq={self.seq} payload={self.payload[:16].hex()}"
        )


class DumlDecoder:
    """Incremental DUML v1 frame decoder with CRC validation and resync."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._dropped = 0

    @property
    def dropped_bytes(self) -> int:
        return self._dropped

    def reset(self) -> None:
        self._buf.clear()
        self._dropped = 0

    def push(self, data: bytes) -> None:
        if data:
            self._buf.extend(data)
        if len(self._buf) > _MAX_CONTROL_BUFFER:
            drop = len(self._buf) - _MAX_CONTROL_BUFFER // 2
            del self._buf[:drop]
            self._dropped += drop

    def next_frame(self) -> DumlFrame | None:
        while True:
            pos = self._buf.find(SOF)
            if pos < 0:
                self._dropped += len(self._buf)
                self._buf.clear()
                return None
            if pos:
                del self._buf[:pos]
                self._dropped += pos
            if len(self._buf) < 4:
                return None
            length = int.from_bytes(self._buf[1:3], "little") & 0x3FF
            if length < DUML_OVERHEAD or crc8(bytes(self._buf[:3])) != self._buf[3]:
                del self._buf[:1]
                self._dropped += 1
                continue
            if len(self._buf) < length:
                return None
            body = bytes(self._buf[: length - 2])
            expected = int.from_bytes(self._buf[length - 2 : length], "little")
            if crc16(body) != expected:
                del self._buf[:1]
                self._dropped += 1
                continue
            frame = DumlFrame(
                version=(int.from_bytes(self._buf[1:3], "little") >> 10) & 0x3F,
                sender=self._buf[4] & 0x1F,
                sender_index=self._buf[4] >> 5,
                receiver=self._buf[5] & 0x1F,
                receiver_index=self._buf[5] >> 5,
                seq=int.from_bytes(self._buf[6:8], "little"),
                is_ack=bool(self._buf[8] & 0x80),
                ack_policy=(self._buf[8] >> 5) & 0x03,
                cmd_set=self._buf[9],
                cmd_id=self._buf[10],
                payload=body[11:],
            )
            del self._buf[:length]
            return frame


def _sysfs_attr(path: str, name: str) -> int | None:
    base = Path("/sys/class/tty") / Path(path).name
    for candidate in (base / "device" / name, base / "device" / ".." / name):
        try:
            return int(candidate.read_text().strip(), 16)
        except (OSError, ValueError):
            continue
    return None


def _interface_number(path: str) -> int | None:
    return _sysfs_attr(path, "bInterfaceNumber")


def _usb_ids(path: str) -> tuple[int | None, int | None]:
    return _sysfs_attr(path, "idVendor"), _sysfs_attr(path, "idProduct")


def find_control_port(preferred: str | None = None) -> str | None:
    """Return the receiver's control tty, preferring CDC interface 2."""
    if preferred:
        return preferred
    candidates = sorted(glob.glob("/dev/ttyACM*"))
    scored: list[tuple[int, str]] = []
    for path in candidates:
        iface = _interface_number(path)
        vid, pid = _usb_ids(path)
        score = 0
        if (vid, pid) == (USB_VID, USB_PID):
            score += 10
        if iface == CONTROL_INTERFACE:
            score += 100
        elif iface is not None:
            score += 1
        scored.append((score, path))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


def _open_control_port(path: str) -> int:
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        tty.setraw(fd, termios.TCSANOW)
        speed = getattr(termios, "B921600", termios.B115200)
        attrs = termios.tcgetattr(fd)
        attrs[4] = attrs[5] = speed
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except Exception:
        os.close(fd)
        raise
    return fd


class ControlLink:
    """Own the DUML control port and send I-frame/pairing requests.

    Failures are non-fatal: the link logs and retries so the video pipeline
    keeps running when the control port is absent or unplugged.
    """

    def __init__(
        self,
        config: ControlConfig,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("vt13_video.control")
        self._fd: int | None = None
        self._port: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._decoder = DumlDecoder()
        self._last_iframe_at = 0.0
        self._last_open_error: str | None = None
        self._rx_logged = 0
        self._counters = {
            "tx_frames": 0,
            "rx_frames": 0,
            "iframe_requests": 0,
            "pairing_queries": 0,
            "errors": 0,
        }
        self._last_frame: DumlFrame | None = None

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="vt13-control", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            self._thread = None
        self._close_port("closed")

    def __enter__(self) -> "ControlLink":
        self.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    # ------------------------------------------------------------------ public API
    @property
    def connected(self) -> bool:
        with self._state_lock:
            return self._fd is not None

    def request_iframe(self, reason: str = "") -> bool:
        if not self.connected:
            return False
        now = time.monotonic()
        if now - self._last_iframe_at < self.config.min_iframe_interval_s:
            return False
        if not self._send(request_iframe_frame(), "iframe"):
            return False
        self._last_iframe_at = now
        with self._state_lock:
            self._counters["iframe_requests"] += 1
        self.logger.info("control: requested I-frame%s", f" ({reason})" if reason else "")
        return True

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            counters = dict(self._counters)
            last = self._last_frame
            fd_open = self._fd is not None
            port = self._port
        return {
            "enabled": True,
            "port": port,
            "connected": fd_open,
            **counters,
            "dropped_bytes": self._decoder.dropped_bytes,
            "last_frame": last.summary if last is not None else None,
            "pairing_poll_s": self.config.pairing_poll_s,
            "iframe_retry_s": self.config.iframe_retry_s,
        }

    # ------------------------------------------------------------------ internals
    def _run(self) -> None:
        next_pairing = time.monotonic()
        while not self._stop.is_set():
            if not self.connected:
                if self._open():
                    next_pairing = time.monotonic()
                else:
                    self._stop.wait(_RECONNECT_INTERVAL_S)
                    continue

            now = time.monotonic()
            if self.config.pairing_poll_s > 0 and now >= next_pairing:
                if self._send(pairing_query_frame(), "pairing"):
                    with self._state_lock:
                        self._counters["pairing_queries"] += 1
                    self.logger.debug("control: pairing query")
                next_pairing = now + self.config.pairing_poll_s

            with self._state_lock:
                fd = self._fd
            if fd is None:
                continue
            try:
                readable, _, _ = select.select([fd], [], [], _READ_TIMEOUT_S)
            except (OSError, ValueError) as exc:
                self._close_port(f"select failed: {exc}")
                continue
            if not readable:
                continue
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                continue
            except OSError as exc:
                self._close_port(f"read failed: {exc}")
                continue
            if not data:
                self._close_port("endpoint closed")
                continue
            self._decoder.push(data)
            while True:
                frame = self._decoder.next_frame()
                if frame is None:
                    break
                self._on_frame(frame)

    def _open(self) -> bool:
        port = find_control_port(self.config.port)
        if port is None:
            message = "no /dev/ttyACM* control port found"
            if message != self._last_open_error:
                self.logger.warning("control link unavailable: %s", message)
                self._last_open_error = message
            return False
        try:
            fd = _open_control_port(port)
        except OSError as exc:
            message = f"cannot open {port}: {exc}"
            if message != self._last_open_error:
                self.logger.warning("control link unavailable: %s", message)
                self._last_open_error = message
            with self._state_lock:
                self._counters["errors"] += 1
            return False
        with self._write_lock:
            self._fd = fd
        with self._state_lock:
            self._port = port
        self._decoder.reset()
        self._last_open_error = None
        iface = _interface_number(port)
        self.logger.info("control link open: %s (interface %s)", port, iface)
        if self.config.iframe_on_connect:
            self.request_iframe("control_open")
        return True

    def _send(self, frame: bytes, kind: str) -> bool:
        written = 0
        error: OSError | None = None
        with self._write_lock:
            fd = self._fd
            if fd is None:
                return False
            try:
                written = os.write(fd, frame)
            except BlockingIOError:
                try:
                    select.select([], [fd], [], 0.05)
                    written = os.write(fd, frame)
                except OSError as exc:
                    error = exc
            except OSError as exc:
                error = exc
        if error is not None:
            self._fail_write(kind, error)
            return False
        if written != len(frame):
            self.logger.warning("control: short %s write (%d/%d)", kind, written, len(frame))
            return False
        with self._state_lock:
            self._counters["tx_frames"] += 1
        return True

    def _fail_write(self, kind: str, exc: BaseException) -> None:
        self.logger.warning("control: %s write failed: %r", kind, exc)
        with self._state_lock:
            self._counters["errors"] += 1
        # The reader thread reopens the port after a write failure.
        try:
            self._close_port("write failed")
        except Exception:
            pass

    def _on_frame(self, frame: DumlFrame) -> None:
        with self._state_lock:
            self._counters["rx_frames"] += 1
            self._last_frame = frame
            self._rx_logged += 1
            logged = self._rx_logged
        if logged <= 3:
            self.logger.info("control rx: %s", frame.summary)
        else:
            self.logger.debug("control rx: %s", frame.summary)

    def _close_port(self, reason: str) -> None:
        with self._write_lock:
            fd = self._fd
            self._fd = None
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        with self._state_lock:
            was_open = self._port is not None
            self._port = None
        if was_open and reason not in {"closed"}:
            self.logger.warning("control link lost: %s", reason)
