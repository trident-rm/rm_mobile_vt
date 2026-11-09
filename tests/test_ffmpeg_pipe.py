from __future__ import annotations

import os
import shutil
import unittest
from unittest import mock

from vt13_video.config import AppConfig
from vt13_video.pipeline import VT13Stream
from vt13_video.sources import FileSource

from .helpers import GOLDEN_CAPTURE

try:
    import av  # noqa: F401
    import cv2  # noqa: F401
    import numpy as np

    _HAS_DEPS = True
except ImportError:
    _HAS_DEPS = False


def _run_golden_pipe(config: AppConfig) -> tuple[VT13Stream, list]:
    source = FileSource(GOLDEN_CAPTURE, read_size=config.read.read_size)
    stream = VT13Stream(config, source=source)
    stream.start()
    stream.join(60.0)
    if stream.is_running:
        stream.stop()
        stream.join(5.0)
    frames = []
    while True:
        frame = stream.read_frame(0)
        if frame is None:
            break
        frames.append(frame)
    return stream, frames


def _pipe_config() -> AppConfig:
    config = AppConfig()
    config.output.preview = False
    config.decoder.backend = "ffmpeg-pipe"
    config.decoder.ffmpeg_path = shutil.which("ffmpeg")
    config.decoder.ffmpeg_codec = "hevc"
    config.decoder.queue_size = 256
    config.decoder.drop_oldest = False
    return config


@unittest.skipUnless(_HAS_DEPS, "av and cv2 are required for the ffmpeg-pipe backend")
@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg binary is unavailable")
@unittest.skipUnless(GOLDEN_CAPTURE.is_file(), "golden capture is unavailable")
class FfmpegPipeGoldenTests(unittest.TestCase):
    def test_golden_replay_via_pipe_software_codec(self) -> None:
        config = _pipe_config()
        stream, frames = _run_golden_pipe(config)
        self.assertFalse(stream.is_running, "pipeline did not finish before timeout")
        self.assertEqual(len(frames), 105)
        self.assertEqual(frames[0].width, 1832)
        self.assertEqual(frames[0].height, 1032)
        self.assertEqual(frames[-1].width, 1920)
        self.assertEqual(frames[-1].height, 1080)
        snap = stream.decoder.snapshot()
        self.assertEqual(snap["backend"], "ffmpeg-pipe")
        self.assertEqual(snap["errors"], 0)
        self.assertEqual(snap["frames_decoded"], 105)

    def test_display_degrades_gracefully_without_x(self) -> None:
        config = _pipe_config()
        config.decoder.display = "ffplay"
        env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "XAUTHORITY")}
        with mock.patch.dict(os.environ, env, clear=True):
            stream, frames = _run_golden_pipe(config)
        self.assertEqual(len(frames), 105)
        snap = stream.decoder.snapshot()
        self.assertEqual(snap["errors"], 0)
        self.assertIn(snap["display"], ("disabled", "none", "ffplay"))


@unittest.skipUnless(_HAS_DEPS, "av and numpy are required")
class Nv12PackTests(unittest.TestCase):
    def test_pack_nv12_strips_stride_padding(self) -> None:
        from vt13_video.ffmpeg_pipe import FfmpegPipeDecoder

        frame = av.VideoFrame(64, 48, "nv12")
        p0, p1 = frame.planes[0], frame.planes[1]
        y = np.frombuffer(p0, dtype=np.uint8).reshape(48, p0.line_size)
        y[:, :64] = np.arange(48 * 64, dtype=np.uint8).reshape(48, 64)
        y[:, 64:] = 255
        uv = np.frombuffer(p1, dtype=np.uint8).reshape(24, p1.line_size)
        uv[:, :64] = 7
        uv[:, 64:] = 255
        packed = FfmpegPipeDecoder._pack_nv12(frame, np)
        self.assertEqual(packed.shape, (72, 64))
        self.assertTrue((packed[:48] == y[:, :64]).all())
        self.assertTrue((packed[48:] == 7).all())


@unittest.skipUnless(_HAS_DEPS, "av and cv2 are required")
class FfmpegPipeResetTests(unittest.TestCase):
    def test_reset_keeps_display_and_defers_spawn(self) -> None:
        import logging
        import queue

        from vt13_video.config import DecoderConfig
        from vt13_video.ffmpeg_pipe import FfmpegPipeDecoder

        decoder = object.__new__(FfmpegPipeDecoder)
        decoder.config = DecoderConfig()
        decoder.logger = logging.getLogger("test")
        decoder._proc = None
        decoder._frame_q = queue.Queue()
        decoder._reader = None
        decoder._stderr_thread = None
        decoder._reader_error = "stale"
        decoder._au_context = None
        decoder._pipe_dropped = 0
        decoder._terminated = False
        decoder._last_sps_hash = None
        decoder._display_proc = object()
        decoder._display_dims = (1920, 1080)
        decoder._display_disabled = False
        decoder.needs_keyframe = False
        decoder.waiting_reason = None
        decoder.errors = 0
        decoder.consecutive_errors = 2
        decoder.resets = 0
        decoder.frames_decoded = 0
        decoder.corrupt_frames = 0
        decoder.sequence = 0
        decoder._au_index = 0

        decoder.reset()

        self.assertTrue(decoder.needs_keyframe)
        self.assertEqual(decoder.resets, 1)
        self.assertEqual(decoder.consecutive_errors, 0)
        self.assertIsNone(decoder._proc)
        self.assertIsNone(decoder._ctx)
        self.assertIsNotNone(decoder._display_proc)
        self.assertIsNone(decoder._reader_error)


@unittest.skipUnless(_HAS_DEPS, "numpy is required")
class DisplayFrameTests(unittest.TestCase):
    def test_green_curtain_detection(self) -> None:
        from vt13_video.ffmpeg_pipe import FfmpegPipeDecoder

        zeros = np.zeros((72, 64), dtype=np.uint8)
        self.assertTrue(FfmpegPipeDecoder._looks_like_green_curtain(zeros))
        normal = np.full((72, 64), 128, dtype=np.uint8)
        normal[:48] = 80
        self.assertFalse(FfmpegPipeDecoder._looks_like_green_curtain(normal))

        grey = np.full((72, 64), 128, dtype=np.uint8)
        self.assertTrue(FfmpegPipeDecoder._looks_like_grey_frame(grey))
        self.assertFalse(FfmpegPipeDecoder._looks_like_grey_frame(normal))

        partial = np.full((72, 64), 128, dtype=np.uint8)
        partial[:24] = 80            # top half of Y is valid
        partial[24:48] = 0           # bottom half of Y is zero/green
        partial[48:60] = 128         # top half of UV is valid
        partial[60:] = 0             # bottom half of UV is zero/green
        self.assertTrue(FfmpegPipeDecoder._looks_like_partial_green(partial))
        self.assertFalse(FfmpegPipeDecoder._looks_like_partial_green(normal))


if __name__ == "__main__":
    unittest.main()