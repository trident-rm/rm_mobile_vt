from __future__ import annotations

import os
import pty
import select
import time
import unittest

from vt13_video.config import ControlConfig
from vt13_video.control import (
    ControlLink,
    DumlDecoder,
    crc8,
    crc16,
    find_control_port,
    pairing_query_frame,
    request_iframe_frame,
)

# First frame of captures/cold_start/serial_ttyACM0.bin (receiver -> PC).
REAL_FRAME = bytes.fromhex("550e04660e020dea10090800dc95")


class DumlFrameTests(unittest.TestCase):
    def test_request_frame_matches_official_client(self) -> None:
        self.assertEqual(
            request_iframe_frame().hex(),
            "55170438aa0e0000400101000000000024000000248f06",
        )
        self.assertEqual(
            pairing_query_frame().hex(),
            "550f04a2aa0e00004009550002e742",
        )

    def test_crc_primitives_match_rm_receiver(self) -> None:
        self.assertEqual(crc8(b"123456789", 0x00), 0xA1)
        self.assertEqual(crc16(b"123456789", 0xFFFF), 0x6F91)
        self.assertEqual(len(request_iframe_frame()), 23)

    def test_decoder_parses_real_frame_and_resyncs(self) -> None:
        decoder = DumlDecoder()
        decoder.push(b"\x00\x55\x99" + REAL_FRAME + b"\xff" + REAL_FRAME[:5])
        decoder.push(REAL_FRAME[5:])
        frames = []
        while (frame := decoder.next_frame()) is not None:
            frames.append(frame)
        self.assertEqual(len(frames), 2)
        self.assertEqual((frames[0].cmd_set, frames[0].cmd_id), (9, 8))
        self.assertEqual((frames[0].sender, frames[0].receiver), (14, 2))
        self.assertEqual(frames[0].payload, b"\x00")
        self.assertGreater(decoder.dropped_bytes, 0)

    def test_decoder_handles_split_reads(self) -> None:
        decoder = DumlDecoder()
        frames = []
        for i in range(0, len(REAL_FRAME), 3):
            decoder.push(REAL_FRAME[i : i + 3])
            frames.extend(
                frame for frame in iter(decoder.next_frame, None)
            )
        self.assertEqual(len(frames), 1)

    def test_preferred_port_is_passed_through(self) -> None:
        self.assertEqual(find_control_port("/dev/ttyACM9"), "/dev/ttyACM9")


class ControlLinkPtyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.master, self.slave = pty.openpty()
        self.port = os.ttyname(self.slave)
        os.set_blocking(self.master, False)
        self.link = ControlLink(
            ControlConfig(
                enabled=True,
                port=self.port,
                pairing_poll_s=0.1,
                min_iframe_interval_s=0.0,
            )
        )

    def tearDown(self) -> None:
        self.link.close()
        os.close(self.master)
        os.close(self.slave)

    def _read(self, duration: float) -> bytes:
        data = b""
        deadline = time.time() + duration
        while time.time() < deadline:
            readable, _, _ = select.select([self.master], [], [], 0.05)
            if readable:
                try:
                    data += os.read(self.master, 4096)
                except OSError:
                    break
        return data

    def test_connect_sends_iframe_and_pairing(self) -> None:
        self.link.start()
        data = self._read(0.8)
        self.assertIn(request_iframe_frame(), data)
        self.assertIn(pairing_query_frame(), data)
        self.assertTrue(self.link.connected)

    def test_decodes_downlink_frames(self) -> None:
        self.link.start()
        self._read(0.3)
        os.write(self.master, REAL_FRAME)
        deadline = time.time() + 1.0
        while time.time() < deadline and self.link.snapshot()["rx_frames"] == 0:
            time.sleep(0.02)
        snapshot = self.link.snapshot()
        self.assertEqual(snapshot["rx_frames"], 1)
        self.assertIn("09/08", snapshot["last_frame"])

    def test_request_iframe_is_rate_limited(self) -> None:
        self.link.config.min_iframe_interval_s = 10.0
        self.link.config.iframe_on_connect = False
        self.link.start()
        self._read(0.3)
        self.assertTrue(self.link.request_iframe("first"))
        before = self.link.snapshot()["iframe_requests"]
        self.assertFalse(self.link.request_iframe("second"))
        self.assertEqual(self.link.snapshot()["iframe_requests"], before)


if __name__ == "__main__":
    unittest.main()
