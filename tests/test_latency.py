from __future__ import annotations

import logging
import socket
import struct
import tempfile
import unittest
from pathlib import Path

from vt13_video.nal import AccessUnit, AccessUnitAssembler, parse_nal
from vt13_video.worker_client import FLAG_IRAP, MAGIC, LatencyCsv, WorkerDecoder

from .helpers import make_nal


def _au(nal_type: int, *, received_at: float, completed_at: float | None) -> AccessUnit:
    raw = make_nal(nal_type, b"\x00", first_slice=nal_type <= 31)
    nal = parse_nal(raw, 4 if raw.startswith(b"\x00\x00\x00\x01") else 3)
    assert nal is not None
    return AccessUnit((nal,), received_at, completed_at)


class CompletedAtTests(unittest.TestCase):
    def test_assembler_stamps_emission_trigger(self) -> None:
        assembler = AccessUnitAssembler()
        first = parse_nal(make_nal(1, b"\x00", first_slice=True), 3)
        second = parse_nal(make_nal(35, b"\x30"), 3)
        assert first is not None and second is not None
        self.assertEqual(assembler.feed(first, 1.0), [])
        out = assembler.feed(second, 1.5)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].received_at, 1.0)
        self.assertEqual(out[0].completed_at, 1.5)

    def test_flush_has_no_completed_at(self) -> None:
        assembler = AccessUnitAssembler()
        nal = parse_nal(make_nal(1, b"\x00", first_slice=True), 3)
        assert nal is not None
        assembler.feed(nal, 2.0)
        out = assembler.flush()
        self.assertEqual(len(out), 1)
        self.assertIsNone(out[0].completed_at)


class LatencyCsvTests(unittest.TestCase):
    def test_rows_are_written_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lat.csv"
            csv = LatencyCsv(str(path))
            csv.au(7, 1_000, 2_000, FLAG_IRAP, 21_000)
            csv.event("rec", 7, 3_000, 4)
            csv.close()
            lines = path.read_text().splitlines()
            self.assertEqual(lines[0].split("\t"), [
                "kind", "seq", "mono_ns", "completed_ns", "flags", "bytes",
                "received_ns", "au_start_ns", "sender_ns",
            ])
            au = lines[1].split("\t")
            self.assertEqual(au[:3], ["au", "7", "2000"])
            self.assertEqual(au[3:], ["1000", "1", "21000", "-1", "-1", "-1"])
            rec = lines[2].split("\t")
            self.assertEqual(rec[:3], ["rec", "7", "3000"])
            self.assertEqual(rec[5], "4")


class _FakeWorker:
    """WorkerDecoder with a socketpair instead of a spawned d3_probe."""

    def __init__(self) -> None:
        self.decoder = object.__new__(WorkerDecoder)
        self.peer: socket.socket
        d = self.decoder
        d.config = None
        d.logger = logging.getLogger("test-worker")
        d._on_recover = None
        d.recoveries = 0
        d.errors = 0
        d.resets = 0
        d.frames_decoded = 0
        d.corrupt_frames = 0
        d.needs_keyframe = True
        d.waiting_reason = "worker_start"
        d.dropped_aus = 0
        d._seq = 0
        d._au_index = 0
        d._dropping = False
        d._sock_path = None
        d._srv = None
        d._proc = None
        d._lat = None
        sock, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        sock.setblocking(False)
        peer.setblocking(False)
        d._conn = sock
        self.peer = peer

    def recv_header(self) -> tuple[tuple[int, ...], bytes]:
        msg = self.peer.recv(64 * 1024)
        magic, length, seq, flags, ts = struct.unpack("<IIIIQ", msg[:24])
        self.last_seq = seq
        self.last_ts = ts
        return (magic, length, seq, flags, ts), msg[24:]

    def close(self) -> None:
        self.decoder._conn.close()
        self.peer.close()
        if self.decoder._lat is not None:
            self.decoder._lat.close()


class WorkerLatencyLogTests(unittest.TestCase):
    def test_decode_writes_matching_au_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = _FakeWorker()
            try:
                fake.decoder._lat = LatencyCsv(str(Path(tmp) / "lat.csv"))
                au = _au(19, received_at=10.0, completed_at=10.25)
                frames = fake.decoder.decode(au)
                self.assertEqual(len(frames), 1)
                header, _ = fake.recv_header()
                self.assertEqual(header[0], MAGIC)
                self.assertEqual(header[2], 0)
                self.assertEqual(header[3], FLAG_IRAP)
                self.assertEqual(header[4], fake.last_ts)
            finally:
                fake.close()
            lines = (Path(tmp) / "lat.csv").read_text().splitlines()
            au_row = lines[1].split("\t")
            self.assertEqual(au_row[0], "au")
            self.assertEqual(au_row[1], "0")
            self.assertEqual(int(au_row[2]), fake.last_ts)
            self.assertEqual(int(au_row[3]), 10_250_000_000)

    def test_recover_event_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = _FakeWorker()
            recovered: list[int] = []
            fake.decoder._on_recover = lambda: recovered.append(1)
            try:
                fake.decoder._lat = LatencyCsv(str(Path(tmp) / "lat.csv"))
                fake.peer.send(b"R")
                fake.decoder._drain_events()
                self.assertEqual(fake.decoder.recoveries, 1)
                self.assertEqual(recovered, [1])
            finally:
                fake.close()
            rows = (Path(tmp) / "lat.csv").read_text().splitlines()
            self.assertEqual(rows[1].split("\t")[0], "rec")

    def test_no_csv_by_default(self) -> None:
        fake = _FakeWorker()
        try:
            self.assertIsNone(fake.decoder._lat)
        finally:
            fake.close()

    def test_env_enables_csv_at_construction(self) -> None:
        from unittest import mock
        import os

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lat.csv"
            with mock.patch.dict(os.environ, {"VT13_LAT_CSV": str(path)}):
                with mock.patch.object(WorkerDecoder, "_start", lambda self: None):
                    decoder = WorkerDecoder(None)
            self.assertIsNotNone(decoder._lat)
            decoder._lat.close()
            self.assertEqual(
                path.read_text().splitlines()[0].split("\t")[0], "kind"
            )


if __name__ == "__main__":
    unittest.main()
