from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import tempfile
import time
import unittest

from vt13_video.config import AppConfig, ControlConfig, DecoderConfig, RecoveryConfig
from vt13_video.decoder import HevcDecoder
from vt13_video.nal import AccessUnit, scan_nals
from vt13_video.pipeline import RecordingError, VT13Stream
from vt13_video.recovery import RecoveryController
from vt13_video.sources import ReadResult, UsbReadError

from .helpers import (
    GOLDEN_CAPTURE,
    make_nal,
    make_non_irap_chunk,
    run_stream,
    strip_parameter_sets,
)


try:
    import av  # noqa: F401

    _HAS_AV = True
except ImportError:
    _HAS_AV = False


class _FakeSource:
    identity = "fake-device"

    def open(self) -> None:
        pass

    def read(self) -> ReadResult:
        return ReadResult(b"", time.monotonic(), eof=True)

    def close(self) -> None:
        pass

    def drain(self, count: int) -> bytes:
        return b""

    def clear_halt(self) -> bool:
        return True

    def reset_device(self) -> bool:
        return True


class _ScriptedSource:
    identity = "scripted-device"

    def __init__(self, script: list[ReadResult | BaseException]) -> None:
        self.script = list(script)
        self.open_count = 0
        self.close_count = 0
        self.clear_halt_count = 0
        self.reset_count = 0

    def open(self) -> None:
        self.open_count += 1

    def read(self) -> ReadResult:
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def close(self) -> None:
        self.close_count += 1

    def drain(self, count: int) -> bytes:
        return b""

    def clear_halt(self) -> bool:
        self.clear_halt_count += 1
        return True

    def reset_device(self) -> bool:
        self.reset_count += 1
        return True


class _PrerollSource(_FakeSource):
    def __init__(self, preroll: bytes, reads: list[ReadResult] | None = None) -> None:
        self.preroll = preroll
        self.reads = list(
            reads or [ReadResult(b"", time.monotonic(), eof=True)]
        )

    def drain(self, count: int) -> bytes:
        return self.preroll

    def read(self) -> ReadResult:
        return self.reads.pop(0)


@unittest.skipUnless(_HAS_AV, "PyAV is required for decoder tests")
@unittest.skipUnless(GOLDEN_CAPTURE.is_file(), "golden capture is unavailable")
class GoldenReplayTests(unittest.TestCase):
    def test_golden_capture_decodes_expected_frames(self) -> None:
        stream, frames = run_stream(GOLDEN_CAPTURE)
        snapshot = stream.snapshot()

        self.assertEqual(len(frames), 105)
        self.assertEqual(frames[0].width, 1832)
        self.assertEqual(frames[0].height, 1032)
        self.assertEqual(frames[0].image.shape[2], 3)
        self.assertEqual(frames[-1].width, 1920)
        self.assertEqual(frames[-1].height, 1080)

        self.assertEqual(snapshot["decode"]["frames"], 105)
        self.assertEqual(snapshot["decode"]["errors"], 0)
        self.assertEqual(snapshot["decoder"]["errors"], 0)
        self.assertEqual(snapshot["decoder"]["frames_decoded"], 105)
        self.assertEqual(snapshot["stream"]["access_units"], 121)
        self.assertEqual(snapshot["stream"]["irap_access_units"], 3)
        self.assertEqual(snapshot["stream"]["skipped_access_units"], 16)
        self.assertEqual(snapshot["stream"]["keyframe_starts"], 1)
        self.assertEqual(snapshot["stream"]["discontinuities"], 2)
        self.assertTrue(snapshot["link"]["parameter_sets_complete"])
        self.assertTrue(snapshot["link"]["irap_seen"])
        self.assertTrue(snapshot["link"]["keyframe_started"])

    def test_parameter_sets_file_bootstraps_stripped_stream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stripped = strip_parameter_sets(
                GOLDEN_CAPTURE, Path(temp_dir) / "cold_start_noparams.h265"
            )

            stream_without_cache, frames_without_cache = run_stream(stripped)
            snapshot_without_cache = stream_without_cache.snapshot()
            self.assertEqual(frames_without_cache, [])
            self.assertEqual(snapshot_without_cache["decode"]["frames"], 0)
            self.assertEqual(snapshot_without_cache["stream"]["skipped_access_units"], 121)
            self.assertEqual(snapshot_without_cache["decoder"]["errors"], 0)

            stream_with_cache, frames_with_cache = run_stream(
                stripped, parameter_sets_file=GOLDEN_CAPTURE
            )
            snapshot_with_cache = stream_with_cache.snapshot()
            self.assertEqual(len(frames_with_cache), 105)
            self.assertGreater(frames_with_cache[0].width, 0)
            self.assertEqual(snapshot_with_cache["decode"]["frames"], 105)
            self.assertEqual(snapshot_with_cache["stream"]["skipped_access_units"], 16)
            self.assertEqual(snapshot_with_cache["decoder"]["errors"], 0)


@unittest.skipUnless(_HAS_AV, "PyAV is required for decoder tests")
class DecoderCodecSelectionTests(unittest.TestCase):
    def test_default_codec_remains_software_hevc(self) -> None:
        decoder = HevcDecoder(DecoderConfig())
        self.assertEqual(decoder._ctx.codec.name, "hevc")
        self.assertEqual(decoder.snapshot()["codec"], "hevc")

    def test_v4l2m2m_context_is_created_when_available(self) -> None:
        try:
            av.codec.Codec("hevc_v4l2m2m", "r")
        except ValueError:
            self.skipTest("PyAV build lacks the hevc_v4l2m2m decoder")
        decoder = HevcDecoder(DecoderConfig(codec="hevc_v4l2m2m"))
        self.assertEqual(decoder._ctx.codec.name, "hevc_v4l2m2m")
        self.assertEqual(decoder.snapshot()["codec"], "hevc_v4l2m2m")


@unittest.skipUnless(_HAS_AV, "PyAV is required for pipeline tests")
class PipelineStateTests(unittest.TestCase):
    def test_corrupt_frames_are_suppressed_by_default(self) -> None:
        class FakeAVFrame:
            def __init__(self, corrupt: bool) -> None:
                self.is_corrupt = corrupt
                self.width = 2
                self.height = 2
                self.time = None

            def to_ndarray(self, format: str):
                import numpy as np

                return np.zeros((2, 2, 3), dtype=np.uint8)

        class FakeCodecContext:
            def __init__(self, frames: list[FakeAVFrame]) -> None:
                self.frames = frames

            def parse(self, data: bytes):
                return [object()]

            def decode(self, packet):
                return self.frames

        config = AppConfig()
        decoder = HevcDecoder(config.decoder)
        decoder._ctx = FakeCodecContext(
            [FakeAVFrame(False), FakeAVFrame(True), FakeAVFrame(True)]
        )

        frames = decoder._decode_bytes(b"", AccessUnit((), 0.0))

        self.assertEqual(len(frames), 1)
        self.assertFalse(frames[0].corrupt)
        self.assertEqual(decoder.corrupt_frames, 2)
        self.assertEqual(decoder.frames_decoded, 1)

        config.decoder.emit_corrupt_frames = True
        decoder = HevcDecoder(config.decoder)
        decoder._ctx = FakeCodecContext(
            [FakeAVFrame(False), FakeAVFrame(True), FakeAVFrame(True)]
        )

        frames = decoder._decode_bytes(b"", AccessUnit((), 0.0))

        self.assertEqual(len(frames), 3)
        self.assertEqual([frame.corrupt for frame in frames], [False, True, True])
        self.assertEqual(decoder.corrupt_frames, 2)
        self.assertEqual(decoder.frames_decoded, 3)

    def test_successful_read_without_irap_reports_waiting_keyframe(self) -> None:
        config = AppConfig()
        config.output.preview = False
        stream = VT13Stream(config, source=_FakeSource())
        stream._open_source(time.monotonic())

        stream._handle_chunk(ReadResult(make_non_irap_chunk(), time.monotonic()))
        snapshot = stream.snapshot()

        self.assertEqual(snapshot["state"], "waiting_keyframe")
        self.assertEqual(snapshot["stream"]["access_units"], 1)
        self.assertEqual(snapshot["stream"]["skipped_access_units"], 1)
        self.assertTrue(snapshot["decoder"]["needs_keyframe"])
        self.assertTrue(snapshot["link"]["data_flowing"])
        self.assertFalse(snapshot["link"]["parameter_sets_complete"])
        self.assertFalse(snapshot["link"]["irap_seen"])
        self.assertFalse(snapshot["link"]["keyframe_started"])

    def test_parameter_sets_auto_save_and_link_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "params.h265"
            config = AppConfig()
            config.output.preview = False
            config.decoder.save_parameter_sets = path
            stream = VT13Stream(config, source=_FakeSource())
            stream._open_source(time.monotonic())
            parameter_sets = [
                make_nal(32, b"\x01"),
                make_nal(33, b"\x02"),
                make_nal(34, b"\x03"),
            ]
            data = b"".join(parameter_sets + [make_nal(35, b"\x30")])

            stream._handle_chunk(ReadResult(data, time.monotonic()))
            snapshot = stream.snapshot()

            self.assertEqual(path.read_bytes(), b"".join(parameter_sets))
            self.assertTrue(snapshot["parameter_sets"]["saved"])
            self.assertEqual(snapshot["parameter_sets"]["saved_path"], str(path))
            self.assertTrue(snapshot["link"]["usb_open"])
            self.assertTrue(snapshot["link"]["data_flowing"])
            self.assertTrue(snapshot["link"]["parameter_sets_complete"])
            self.assertFalse(snapshot["link"]["irap_seen"])
            self.assertFalse(snapshot["link"]["keyframe_started"])
            self.assertIn("params=yes", stream.status_line())
            self.assertIn("irap=no", stream.status_line())

    @unittest.skipUnless(GOLDEN_CAPTURE.is_file(), "golden capture is unavailable")
    def test_open_preroll_is_parsed_instead_of_discarded(self) -> None:
        config = AppConfig()
        config.output.preview = False
        config.decoder.queue_size = 256
        config.decoder.drop_oldest = False
        config.read.drain_reads = 1
        data = GOLDEN_CAPTURE.read_bytes()
        first_irap = next(nal for nal in scan_nals(data) if nal.is_irap)
        split = data.find(first_irap.raw) + 100
        source = _PrerollSource(
            data[:split],
            [
                ReadResult(data[split:], time.monotonic()),
                ReadResult(b"", time.monotonic(), eof=True),
            ],
        )
        stream = VT13Stream(config, source=source)

        stream.start()
        stream.join(60.0)
        self.assertFalse(stream.is_running)

        frames = []
        while True:
            frame = stream.read_frame(0)
            if frame is None:
                break
            frames.append(frame)

        snapshot = stream.snapshot()
        self.assertEqual(len(frames), 105)
        self.assertTrue(snapshot["link"]["parameter_sets_complete"])
        self.assertTrue(snapshot["link"]["keyframe_started"])
        self.assertEqual(snapshot["stream"]["skipped_access_units"], 16)
        self.assertEqual(snapshot["stream"]["discontinuities"], 0)

    def test_link_keyframe_flags_reset_on_discontinuity(self) -> None:
        config = AppConfig()
        config.output.preview = False
        stream = VT13Stream(config, source=_FakeSource())
        stream._irap_seen_since_reset = True
        stream._keyframe_started_since_reset = True

        stream._mark_discontinuity("test discontinuity")
        snapshot = stream.snapshot()

        self.assertFalse(snapshot["link"]["irap_seen"])
        self.assertFalse(snapshot["link"]["keyframe_started"])

    def test_keyframe_hint_waits_for_current_data_epoch(self) -> None:
        config = AppConfig()
        config.output.preview = False
        logger = logging.getLogger("vt13_video.test_keyframe_hint_epoch")
        stream = VT13Stream(config, source=_FakeSource(), logger=logger)
        stream.stats.start(now=0.0)
        stream._source_open = True
        stream._data_logged = True
        stream._last_data_at = 0.0

        stream._handle_chunk(ReadResult(make_non_irap_chunk(), 0.0))
        self.assertFalse(stream._keyframe_hint_logged)

        stream._mark_discontinuity("reconnect")
        stream._source_open = True
        stream._last_data_at = 20.0
        stream._handle_chunk(ReadResult(make_non_irap_chunk(), 20.0))
        self.assertFalse(stream._keyframe_hint_logged)

        stream._handle_chunk(ReadResult(make_non_irap_chunk(), 29.999))
        self.assertFalse(stream._keyframe_hint_logged)

        with self.assertLogs(logger, level="WARNING") as captured:
            stream._handle_chunk(ReadResult(make_non_irap_chunk(), 30.0))
        self.assertTrue(stream._keyframe_hint_logged)
        self.assertTrue(any("power-cycle VT03" in line for line in captured.output))

    def test_keyframe_hint_names_missing_prerequisite(self) -> None:
        config = AppConfig()
        config.output.preview = False
        logger = logging.getLogger("vt13_video.test_keyframe_hint_text")
        stream = VT13Stream(config, source=_FakeSource(), logger=logger)
        stream.stats.start(now=0.0)
        stream._source_open = True
        stream._waiting_data_since = 0.0
        stream._last_data_at = 10.0

        with self.assertLogs(logger, level="WARNING") as captured:
            stream._refresh_waiting_state(now=10.0)
        self.assertIn("fresh VPS/SPS/PPS + IRAP", captured.output[0])

        parameter_sets = b"".join(
            [make_nal(32, b"\x01"), make_nal(33, b"\x02"), make_nal(34, b"\x03")]
        )
        stream.params.update_all(scan_nals(parameter_sets))
        stream._keyframe_hint_logged = False

        with self.assertLogs(logger, level="WARNING") as captured:
            stream._refresh_waiting_state(now=10.0)
        self.assertIn("power-cycle VT03 to emit a fresh IRAP", captured.output[0])
        self.assertNotIn("VPS/SPS/PPS", captured.output[0])

    def test_keyframe_hint_explains_usb_replug_does_not_reset_vt03(self) -> None:
        config = AppConfig()
        config.output.preview = False
        config.recovery.initial_backoff_s = 0.0
        config.recovery.max_backoff_s = 0.0
        config.recovery.jitter_fraction = 0.0
        logger = logging.getLogger("vt13_video.test_replug_hint")
        stream = VT13Stream(config, source=_FakeSource(), logger=logger)
        stream.stats.start(now=0.0)

        error = UsbReadError(
            "device disconnected", kind="disconnected", errno=19, backend_error_code=-4
        )
        stream._recover(error.kind, str(error), 0.0, error)
        self.assertTrue(stream._disconnect_recovery_pending)

        stream._open_source(1.0)
        self.assertFalse(stream._disconnect_recovery_pending)
        self.assertTrue(stream._reopened_after_disconnect)

        parameter_sets = b"".join(
            [make_nal(32, b"\x01"), make_nal(33, b"\x02"), make_nal(34, b"\x03")]
        )
        stream.params.update_all(scan_nals(parameter_sets))
        stream._source_open = True
        stream._data_logged = True
        stream._waiting_data_since = 1.0
        stream._last_data_at = 10.0

        with self.assertLogs(logger, level="WARNING") as captured:
            stream._refresh_waiting_state(now=11.0)
        self.assertIn("re-plugging only the VT13 USB does not reset VT03", captured.output[0])
        self.assertIn("power-cycle VT03", captured.output[0])

    def test_repeated_io_recovery_logs_are_throttled(self) -> None:
        config = AppConfig()
        config.output.preview = False
        config.recovery.clear_halt_on_error = True
        config.recovery.reset_after_failures = 0
        logger = logging.getLogger("vt13_video.test_io_throttle")
        stream = VT13Stream(config, source=_FakeSource(), logger=logger)
        stream.stats.start(now=0.0)
        error = UsbReadError(
            "input/output error", kind="io", errno=5, backend_error_code=-1
        )

        with self.assertLogs(logger, level="WARNING") as captured:
            for now in (1.0, 1.1, 1.2, 6.1):
                stream._recover(error.kind, str(error), now, error)

        failure_lines = [
            line for line in captured.output if "USB read failure (io)" in line
        ]
        self.assertEqual(len(failure_lines), 2)
        self.assertTrue(
            any(
                "suppressed 2 repeated USB failure details" in line
                for line in captured.output
            )
        )
        self.assertEqual(stream.snapshot()["usb"]["errors"], 4)

    def test_parameter_sets_saved_on_final_flush(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "params.h265"
            config = AppConfig()
            config.output.preview = False
            config.decoder.save_parameter_sets = path
            stream = VT13Stream(config, source=_FakeSource())
            stream._open_source(time.monotonic())
            data = b"".join(
                [
                    make_nal(32, b"\x01"),
                    make_nal(33, b"\x02"),
                    make_nal(34, b"\x03"),
                ]
            )

            stream._handle_chunk(ReadResult(data, time.monotonic()))
            self.assertFalse(path.exists())
            stream._finish()

            self.assertEqual(path.read_bytes(), data)

    def test_clear_halt_and_reset_are_used_for_pipe_errors(self) -> None:
        script = [
            UsbReadError("pipe stalled", kind="pipe"),
            ReadResult(make_non_irap_chunk(), time.monotonic()),
            ReadResult(b"", time.monotonic(), eof=True),
        ]
        source = _ScriptedSource(script)
        config = AppConfig()
        config.output.preview = False
        config.recovery.initial_backoff_s = 0.0
        config.recovery.max_backoff_s = 0.0
        config.recovery.jitter_fraction = 0.0
        config.recovery.healthy_reads = 1
        config.recovery.healthy_seconds = 1.0
        config.recovery.reset_after_failures = 1
        config.recovery.clear_halt_on_error = True

        stream = VT13Stream(config, source=source)
        stream.start()
        stream.join(5.0)
        self.assertFalse(stream.is_running)

        snapshot = stream.snapshot()
        self.assertEqual(source.open_count, 2)
        self.assertEqual(source.clear_halt_count, 1)
        self.assertEqual(source.reset_count, 1)
        self.assertEqual(snapshot["usb"]["errors"], 1)
        self.assertEqual(snapshot["usb"]["recoveries"], 1)
        self.assertEqual(snapshot["usb"]["resets"], 1)
        self.assertEqual(snapshot["usb"]["halt_clears"], 1)
        self.assertEqual(snapshot["usb"]["halt_clear_failures"], 0)
        self.assertEqual(snapshot["recovery"]["reset_count"], 1)

    def test_clear_halt_can_be_disabled(self) -> None:
        script = [
            UsbReadError("pipe stalled", kind="pipe"),
            ReadResult(make_non_irap_chunk(), time.monotonic()),
            ReadResult(b"", time.monotonic(), eof=True),
        ]
        source = _ScriptedSource(script)
        config = AppConfig()
        config.output.preview = False
        config.recovery.initial_backoff_s = 0.0
        config.recovery.max_backoff_s = 0.0
        config.recovery.jitter_fraction = 0.0
        config.recovery.healthy_reads = 1
        config.recovery.healthy_seconds = 1.0
        config.recovery.reset_after_failures = 0
        config.recovery.clear_halt_on_error = False

        stream = VT13Stream(config, source=source)
        stream.start()
        stream.join(5.0)
        self.assertFalse(stream.is_running)

        snapshot = stream.snapshot()
        self.assertEqual(source.clear_halt_count, 0)
        self.assertEqual(source.reset_count, 0)
        self.assertEqual(snapshot["usb"]["halt_clears"], 0)
        self.assertEqual(snapshot["usb"]["resets"], 0)

    def test_clear_halt_is_used_for_io_errors(self) -> None:
        script = [
            UsbReadError(
                "input/output error", kind="io", errno=5, backend_error_code=-1
            ),
            ReadResult(make_non_irap_chunk(), time.monotonic()),
            ReadResult(b"", time.monotonic(), eof=True),
        ]
        source = _ScriptedSource(script)
        config = AppConfig()
        config.output.preview = False
        config.recovery.initial_backoff_s = 0.0
        config.recovery.max_backoff_s = 0.0
        config.recovery.jitter_fraction = 0.0
        config.recovery.healthy_reads = 1
        config.recovery.healthy_seconds = 1.0
        config.recovery.reset_after_failures = 0
        config.recovery.clear_halt_on_error = True

        stream = VT13Stream(config, source=source)
        stream.start()
        stream.join(5.0)
        self.assertFalse(stream.is_running)

        snapshot = stream.snapshot()
        self.assertEqual(source.open_count, 1)
        self.assertEqual(source.clear_halt_count, 1)
        self.assertEqual(snapshot["usb"]["halt_clears"], 1)
        self.assertEqual(snapshot["usb"]["halt_clear_failures"], 0)
        self.assertEqual(snapshot["usb"]["last_error_kind"], "io")
        self.assertEqual(snapshot["usb"]["last_error_errno"], 5)
        self.assertEqual(snapshot["usb"]["recoveries"], 1)
        self.assertEqual(snapshot["stream"]["discontinuities"], 0)
        self.assertIsNone(snapshot["stream"]["last_discontinuity"])
        self.assertEqual(snapshot["decode"]["resets"], 0)
        self.assertEqual(snapshot["decoder"]["resets"], 0)
        self.assertTrue(snapshot["decoder"]["needs_keyframe"])

    def test_allow_corrupt_frames_controls_pyav_output_flag(self) -> None:
        config = AppConfig()
        config.output.preview = False
        stream = VT13Stream(config, source=_FakeSource())
        corrupt_flag = int(av.codec.context.Flags.output_corrupt)
        self.assertTrue(stream.decoder._ctx.flags & corrupt_flag)

        config.decoder.allow_corrupt_frames = False
        stream = VT13Stream(config, source=_FakeSource())
        self.assertFalse(stream.decoder._ctx.flags & corrupt_flag)

    def test_empty_reads_trigger_stall_recovery(self) -> None:
        source = _ScriptedSource([])
        config = AppConfig()
        config.output.preview = False
        config.read.stall_timeout_s = 1.0
        config.recovery.initial_backoff_s = 0.0
        config.recovery.max_backoff_s = 0.0
        config.recovery.jitter_fraction = 0.0
        config.recovery.clear_halt_on_error = False
        config.recovery.reset_after_failures = 0

        stream = VT13Stream(config, source=source)
        stream.stats.start(now=100.0)
        stream._last_data_at = 100.0

        stream._handle_empty_read(100.5)
        snapshot = stream.snapshot()
        self.assertEqual(snapshot["usb"]["empty_reads"], 1)
        self.assertEqual(snapshot["usb"]["errors"], 0)
        self.assertEqual(snapshot["usb"]["recoveries"], 0)

        stream._handle_empty_read(101.0)
        snapshot = stream.snapshot()
        self.assertEqual(snapshot["usb"]["empty_reads"], 2)
        self.assertEqual(snapshot["usb"]["errors"], 1)
        self.assertEqual(snapshot["usb"]["recoveries"], 1)
        self.assertEqual(snapshot["usb"]["last_error_kind"], "stall")
        self.assertEqual(snapshot["usb"]["last_error_reads"], 0)
        self.assertEqual(snapshot["usb"]["last_error_bytes"], 0)
        self.assertAlmostEqual(snapshot["usb"]["last_error_since_data_s"], 1.0)
        self.assertEqual(snapshot["stream"]["discontinuities"], 1)
        self.assertEqual(snapshot["stream"]["last_discontinuity"], "usb_stall")

    def test_recover_records_error_context_and_codes(self) -> None:
        source = _ScriptedSource([])
        config = AppConfig()
        config.output.preview = False
        config.recovery.initial_backoff_s = 0.0
        config.recovery.max_backoff_s = 0.0
        config.recovery.jitter_fraction = 0.0
        config.recovery.clear_halt_on_error = False
        config.recovery.reset_after_failures = 0

        stream = VT13Stream(config, source=source)
        stream.stats.start(now=10.0)
        stream.stats.record_read(4096, 9.0)
        stream.stats.record_timeout()
        stream.stats.record_empty_read()
        stream._last_data_at = 9.0
        error = UsbReadError(
            "input/output error", kind="io", errno=5, backend_error_code=-1
        )

        stream._recover(error.kind, str(error), 10.5, error)
        snapshot = stream.snapshot()

        self.assertEqual(snapshot["usb"]["errors"], 1)
        self.assertEqual(snapshot["usb"]["recoveries"], 1)
        self.assertEqual(snapshot["usb"]["last_error_kind"], "io")
        self.assertEqual(snapshot["usb"]["last_error_errno"], 5)
        self.assertEqual(snapshot["usb"]["last_error_backend_code"], -1)
        self.assertEqual(snapshot["usb"]["last_error_reads"], 1)
        self.assertEqual(snapshot["usb"]["last_error_bytes"], 4096)
        self.assertAlmostEqual(snapshot["usb"]["last_error_since_data_s"], 1.5)
        self.assertEqual(snapshot["usb"]["timeouts"], 1)
        self.assertEqual(snapshot["usb"]["empty_reads"], 1)

    def test_recording_timestamps_include_utc_wall_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            record_path = Path(temp_dir) / "capture.bin"
            source = _ScriptedSource([])
            config = AppConfig()
            config.output.preview = False
            config.output.record = record_path

            stream = VT13Stream(config, source=source)
            stream.stats.start()
            stream._open_recording()
            stream._write_record(b"\x00\x00\x01", stream.stats.started_at + 1.25)
            stream._event("usb_error", "io: errno=5 backend=-1")
            stream._close_recording()

            times_path = record_path.with_suffix(".times.tsv")
            events_path = record_path.with_name(record_path.stem + ".events.tsv")
            times_lines = times_path.read_text(encoding="utf-8").splitlines()
            events_lines = events_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(times_lines[0], "elapsed_s\tchunk_length\twall_time_utc")
        self.assertEqual(events_lines[0], "elapsed_s\tevent\tdetail\twall_time_utc")

        times_fields = times_lines[1].split("\t")
        self.assertEqual(len(times_fields), 3)
        self.assertAlmostEqual(float(times_fields[0]), 1.25)
        self.assertEqual(int(times_fields[1]), 3)
        times_wall = datetime.fromisoformat(times_fields[2])
        self.assertIsNotNone(times_wall.tzinfo)
        self.assertEqual(times_wall.utcoffset().total_seconds(), 0)

        event_fields = events_lines[1].split("\t")
        self.assertEqual(len(event_fields), 4)
        self.assertGreaterEqual(float(event_fields[0]), 0.0)
        self.assertEqual(event_fields[1], "usb_error")
        self.assertEqual(event_fields[2], "io: errno=5 backend=-1")
        event_wall = datetime.fromisoformat(event_fields[3])
        self.assertIsNotNone(event_wall.tzinfo)
        self.assertEqual(event_wall.utcoffset().total_seconds(), 0)

    def test_recording_open_failure_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            blocker = Path(temp_dir) / "not_a_directory"
            blocker.write_text("x", encoding="utf-8")
            record_path = blocker / "capture.bin"
            source = _ScriptedSource([])
            config = AppConfig()
            config.output.preview = False
            config.output.record = record_path

            stream = VT13Stream(config, source=source)
            with self.assertRaises(RecordingError) as raised:
                stream.start()

        message = str(raised.exception)
        self.assertIn(str(record_path), message)
        self.assertIn("writable", message)
        self.assertFalse(stream.is_running)
        self.assertIsNone(stream._record_fh)
        self.assertIsNone(stream._times_fh)
        self.assertIsNone(stream._events_fh)


class _FakeControl:
    def __init__(self) -> None:
        self.reasons: list[str] = []
        self.closed = False

    def request_iframe(self, reason: str = "") -> bool:
        self.reasons.append(reason)
        return True

    def snapshot(self) -> dict:
        return {
            "enabled": True,
            "port": "fake",
            "connected": True,
            "tx_frames": len(self.reasons),
            "rx_frames": 0,
            "iframe_requests": len(self.reasons),
            "pairing_queries": 0,
            "errors": 0,
            "dropped_bytes": 0,
            "last_frame": None,
            "pairing_poll_s": 0.0,
            "iframe_retry_s": 2.0,
        }

    def close(self) -> None:
        self.closed = True


@unittest.skipUnless(_HAS_AV, "PyAV is required for decoder tests")
class ControlRecoveryIntegrationTests(unittest.TestCase):
    def _stream(self, *, stall_restart_s: float = 0.0):
        config = AppConfig()
        config.control = ControlConfig(enabled=True, iframe_retry_s=2.0)
        config.decoder.stall_restart_s = stall_restart_s
        control = _FakeControl()
        stream = VT13Stream(config, source=_FakeSource(), control=control)
        return stream, control

    def test_discontinuity_requests_iframe(self) -> None:
        stream, control = self._stream()
        stream._source_open = True
        stream._last_data_at = time.monotonic()
        stream._mark_discontinuity("test")
        self.assertIn("discontinuity", control.reasons)
        self.assertTrue(stream.decoder.needs_keyframe)

    def test_discontinuity_request_is_throttled(self) -> None:
        stream, control = self._stream()
        stream._source_open = True
        stream._last_data_at = time.monotonic()
        stream._mark_discontinuity("first")
        stream._mark_discontinuity("second")
        self.assertEqual(control.reasons.count("discontinuity"), 1)

    def test_no_iframe_request_when_no_data_is_flowing(self) -> None:
        stream, control = self._stream()
        stream._source_open = True
        stream._last_data_at = time.monotonic() - 10.0
        stream._mark_discontinuity("stall")
        self.assertEqual(control.reasons, [])

    def test_waiting_keyframe_retries_request(self) -> None:
        stream, control = self._stream()
        now = time.monotonic()
        stream.decoder.needs_keyframe = True
        stream._source_open = True
        stream._last_data_at = now
        stream._waiting_data_since = now - 1.0
        stream._next_iframe_at = 0.0
        stream._refresh_waiting_state(now)
        self.assertIn("waiting_keyframe", control.reasons)

    def test_output_stall_watchdog_resets_and_requests(self) -> None:
        stream, control = self._stream(stall_restart_s=1.0)
        now = time.monotonic()
        stream.decoder.needs_keyframe = False
        stream._source_open = True
        stream._last_data_at = now
        stream._last_vcl_au_at = now - 0.1
        stream._last_frame_at = now - 5.0
        stream._decode_started_at = now - 5.0
        stream._data_epoch_started_at = now - 5.0
        stream._check_output_stall(now)
        self.assertEqual(stream._stall_resets, 1)
        self.assertIn("discontinuity", control.reasons)
        self.assertTrue(stream.decoder.needs_keyframe)

    def test_snapshot_exposes_control_and_watchdog(self) -> None:
        stream, _ = self._stream()
        snapshot = stream.snapshot()
        self.assertTrue(snapshot["control"]["enabled"])
        self.assertEqual(snapshot["watchdog"]["output_stall_resets"], 0)

    def test_kernel_abort_line_detection(self) -> None:
        self.assertTrue(
            VT13Stream._is_kernel_abort_line(
                "meson-vdec ... HEVC_LCU_CHECK status=0xf poc=5 idx=1692"
            )
        )
        self.assertTrue(
            VT13Stream._is_kernel_abort_line("meson-vdec ... Aborting decoding session!")
        )
        self.assertFalse(VT13Stream._is_kernel_abort_line("HEVC_REG status=0x8"))

    def test_kernel_abort_triggers_immediate_recovery(self) -> None:
        stream, control = self._stream()
        stream._source_open = True
        stream._last_data_at = time.monotonic()
        stream.decoder.needs_keyframe = False
        stream._kernel_abort_event.set()
        stream._check_kernel_abort()
        self.assertIn("discontinuity", control.reasons)
        self.assertTrue(stream.decoder.needs_keyframe)


class RecoveryControllerTests(unittest.TestCase):
    def test_backoff_remains_bounded_during_long_usb_absence(self) -> None:
        config = RecoveryConfig(jitter_fraction=0.0)
        controller = RecoveryController(config)
        for i in range(10000):
            delay = controller.on_error(float(i), "USB absent")
            self.assertLessEqual(delay, config.max_backoff_s)
        self.assertEqual(delay, config.max_backoff_s)
        self.assertEqual(controller.consecutive_failures, 10000)

    def test_zero_backoff_remains_zero_after_many_failures(self) -> None:
        config = RecoveryConfig(initial_backoff_s=0.0, jitter_fraction=0.0)
        controller = RecoveryController(config)
        for i in range(1100):
            self.assertEqual(controller.on_error(float(i), "USB absent"), 0.0)

    def test_unit_multiplier_keeps_initial_backoff(self) -> None:
        config = RecoveryConfig(multiplier=1.0, jitter_fraction=0.0)
        controller = RecoveryController(config)
        for i in range(1100):
            self.assertEqual(
                controller.on_error(float(i), "USB absent"), config.initial_backoff_s
            )

    def test_backoff_reset_and_healthy_read_recovery(self) -> None:
        config = RecoveryConfig(
            initial_backoff_s=0.5,
            max_backoff_s=2.0,
            multiplier=2.0,
            jitter_fraction=0.0,
            healthy_reads=3,
            healthy_seconds=100.0,
            reset_after_failures=2,
        )
        controller = RecoveryController(config)

        self.assertAlmostEqual(controller.on_error(1.0, "first"), 0.5)
        self.assertAlmostEqual(controller.on_error(2.0, "second"), 1.0)
        self.assertAlmostEqual(controller.on_error(3.0, "third"), 2.0)
        self.assertAlmostEqual(controller.on_error(4.0, "fourth"), 2.0)
        self.assertTrue(controller.should_reset())
        controller.mark_reset()
        self.assertFalse(controller.should_reset())
        self.assertEqual(controller.reset_count, 1)

        controller.on_open_success(5.0)
        self.assertEqual(controller.consecutive_failures, 4)
        self.assertFalse(controller.on_read_success(5.0))
        self.assertFalse(controller.on_read_success(6.0))
        self.assertTrue(controller.on_read_success(7.0))
        self.assertEqual(controller.consecutive_failures, 0)
        self.assertEqual(controller.healthy_reads, 0)

        self.assertAlmostEqual(controller.on_error(8.0, "after recovery"), 0.5)
        self.assertAlmostEqual(controller.on_error(9.0, "after recovery"), 1.0)
        self.assertTrue(controller.should_reset())


if __name__ == "__main__":
    unittest.main()
