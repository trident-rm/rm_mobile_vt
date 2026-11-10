"""D3b worker backend: send access units to the native V4L2/KMS worker.

The worker is `build/d3/d3_probe --socket ... --hide-primary`; it owns the
V4L2 decode session and the KMS overlay. This class is the pipeline-side
client. It deliberately does not return real pixels: the worker displays
them, and the pipeline only needs frame counters/metadata for its stats.
"""
from __future__ import annotations

import atexit
import logging
import os
import socket
import struct
import subprocess
import time
from pathlib import Path

from .decoder import Frame
from .nal import AccessUnit

MAGIC = 0x44574155
FLAG_IRAP = 1
FLAG_EOS = 2
_HDR = struct.Struct("<IIIIQ")

DEFAULT_SOCKET = "~/mobile_vt/.codex_tmp/d3_worker.sock"
DEFAULT_WORKER = "~/mobile_vt/build/d3/d3_probe"
SEND_STALL_S = 0.02


class WorkerDecoder:
    def __init__(self, config, logger: logging.Logger | None = None, on_recover=None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._on_recover = on_recover
        self.recoveries = 0
        self.errors = 0
        self.resets = 0
        self.frames_decoded = 0
        self.corrupt_frames = 0
        self.needs_keyframe = True
        self.waiting_reason = "worker_start"
        self.dropped_aus = 0
        self._seq = 0
        self._au_index = 0
        self._dropping = False
        self._sock_path: str | None = None
        self._srv: socket.socket | None = None
        self._conn: socket.socket | None = None
        self._proc: subprocess.Popen | None = None
        self._start()
        atexit.register(self._stop)

    # ------------------------------------------------------------- lifecycle
    def _worker_path(self) -> str:
        path = getattr(self.config, "worker_path", None) or DEFAULT_WORKER
        return os.path.expanduser(path)

    def _socket_path(self) -> str:
        path = getattr(self.config, "worker_socket", None) or DEFAULT_SOCKET
        return os.path.expanduser(path)

    def _start(self) -> None:
        path = self._socket_path()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        srv.bind(path)
        srv.listen(1)
        self._srv = srv
        self._sock_path = path
        args = [
            self._worker_path(),
            "--socket", path,
            "--cap-bufs", "17",
            "--video", "1920x1080",
            "--frames", "0",
        ]
        mode = os.environ.get("VT13_WORKER_MODE")
        if mode:
            args += ["--mode", mode]
        if os.environ.get("VT13_WORKER_NO_DISPLAY") == "1":
            args.append("--no-display")
        else:
            args.append("--hide-primary")
        self.logger.info("starting d3 worker: %s", " ".join(args))
        self._proc = subprocess.Popen(args, stdin=subprocess.DEVNULL)
        srv.settimeout(10.0)
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            self.logger.error("d3 worker did not connect to %s", path)
            self._stop()
            raise
        conn.setblocking(False)
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
        except OSError:
            pass
        self._conn = conn
        self.needs_keyframe = True
        self.waiting_reason = "waiting_keyframe"

    def _stop(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._srv is not None:
            try:
                self._srv.close()
            except OSError:
                pass
            self._srv = None
        if self._sock_path:
            try:
                os.unlink(self._sock_path)
            except FileNotFoundError:
                pass
            self._sock_path = None

    def _send(self, payload: bytes, flags: int) -> None:
        assert self._conn is not None
        msg = _HDR.pack(MAGIC, len(payload), self._seq, flags, time.monotonic_ns()) + payload
        self._seq += 1
        deadline = time.monotonic() + SEND_STALL_S
        while True:
            try:
                self._conn.send(msg)
                return
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("worker socket backpressure")
                time.sleep(0.001)

    # ------------------------------------------------------------- decoder API
    def _drain_events(self) -> None:
        if self._conn is None:
            return
        while True:
            try:
                msg = self._conn.recv(16, socket.MSG_DONTWAIT)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            if not msg:
                return
            if msg == b"R":
                self.recoveries += 1
                if self._on_recover is not None:
                    try:
                        self._on_recover()
                    except Exception:  # noqa: BLE001
                        pass

    def decode(self, au: AccessUnit, bootstrap_bytes: bytes = b"") -> list[Frame]:
        self._drain_events()
        irap = au.has_irap
        if self._dropping and not irap:
            self.dropped_aus += 1
            return []
        if self._dropping and irap:
            self._dropping = False
        payload = au.wire_bytes
        if irap and bootstrap_bytes:
            payload = bytes(bootstrap_bytes) + payload
        if len(payload) > 512 * 1024:
            self.dropped_aus += 1
            return []
        try:
            self._send(payload, FLAG_IRAP if irap else 0)
        except TimeoutError:
            # Worker is behind (socket buffer full). Drop this and all
            # following non-IRAP AUs until the next IRAP; do NOT restart.
            self.dropped_aus += 1
            self._dropping = True
            return []
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            self.errors += 1
            self._dropping = True
            self.needs_keyframe = True
            self.waiting_reason = "worker_error"
            self.logger.warning("worker died (%r); restarting", exc)
            try:
                self._stop()
                self._start()
            except Exception as exc2:  # noqa: BLE001
                self.logger.error("worker restart failed: %r", exc2)
            return []
        if irap:
            self.needs_keyframe = False
            self.waiting_reason = ""
        if not au.has_vcl:
            return []
        now = time.monotonic()
        frame = Frame(
            image=None,
            sequence=self.frames_decoded,
            width=1920,
            height=1080,
            received_at=au.received_at,
            decoded_at=now,
            pts=None,
            keyframe=irap,
            au_index=self._au_index,
            latency_s=max(0.0, now - au.received_at),
            corrupt=False,
        )
        self.frames_decoded += 1
        self._au_index += 1
        return [frame]

    def reset(self) -> None:
        self.resets += 1
        self.needs_keyframe = True
        self.waiting_reason = "waiting_keyframe"
        # A live worker rebuilds its V4L2 session in-process; only a dead
        # worker needs a process restart.
        if self._proc is not None and self._proc.poll() is None:
            return
        self._stop()
        try:
            self._start()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("worker restart failed: %r", exc)

    def flush(self) -> list[Frame]:
        if self._conn is not None:
            try:
                self._send(b"", FLAG_EOS)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._proc.wait(timeout=2) if self._proc is not None else None
            except Exception:  # noqa: BLE001
                pass
        self._stop()
        return []

    def snapshot(self) -> dict:
        return {
            "backend": "worker",
            "frames_decoded": self.frames_decoded,
            "errors": self.errors,
            "resets": self.resets,
            "dropped_aus": self.dropped_aus,
            "needs_keyframe": self.needs_keyframe,
            "waiting_reason": self.waiting_reason,
            "worker_pid": self._proc.pid if self._proc is not None else None,
        }
