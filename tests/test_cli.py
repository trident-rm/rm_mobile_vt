from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import vt13_video.cli as cli_module
from vt13_video.config import AppConfig, load_config
from vt13_video.device import DiscoveryResult, UsbDeviceInfo
from vt13_video.sources import FileSource

from .helpers import GOLDEN_CAPTURE, make_non_irap_chunk


try:
    import av  # noqa: F401

    _HAS_AV = True
except ImportError:
    _HAS_AV = False


class CliSmokeTests(unittest.TestCase):
    def test_config_json_output(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            return_code = cli_module.main(["config", "--json"])

        self.assertEqual(return_code, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["device"]["vid"], 0x2CA3)
        self.assertEqual(payload["device"]["pid"], 0x1020)
        self.assertEqual(payload["decoder"]["output_format"], "bgr24")

    def test_write_default_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "vt13.yaml"
            output = io.StringIO()
            with redirect_stdout(output):
                return_code = cli_module.main(
                    ["config", "--write-default", str(config_path)]
                )

            self.assertEqual(return_code, 0)
            self.assertTrue(config_path.is_file())
            config = load_config(config_path)
            self.assertEqual(config.device.endpoint, 0x81)
            self.assertTrue(config.recovery.clear_halt_on_error)

    @unittest.skipUnless(GOLDEN_CAPTURE.is_file(), "golden capture is unavailable")
    def test_replay_command_builds_file_source(self) -> None:
        with patch.object(cli_module, "_run_pipeline", return_value=0) as runner:
            return_code = cli_module.main(
                [
                    "replay",
                    "--file",
                    str(GOLDEN_CAPTURE),
                    "--headless",
                    "--json-stats",
                ]
            )

        self.assertEqual(return_code, 0)
        config, source, arguments = runner.call_args.args
        self.assertIsInstance(source, FileSource)
        self.assertEqual(source.path, GOLDEN_CAPTURE.resolve())
        self.assertFalse(config.output.preview)
        self.assertFalse(config.decoder.drop_oldest)
        self.assertGreaterEqual(config.decoder.queue_size, 256)
        self.assertTrue(arguments.json_stats)

    def test_save_parameter_sets_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "params.h265"
            with patch.object(cli_module, "_run_pipeline", return_value=0) as runner:
                return_code = cli_module.main(
                    [
                        "stream",
                        "--headless",
                        "--save-parameter-sets",
                        str(target),
                    ]
                )

        self.assertEqual(return_code, 0)
        config, source, arguments = runner.call_args.args
        self.assertIsNone(source)
        self.assertEqual(config.decoder.save_parameter_sets, target.resolve())

    @unittest.skipUnless(_HAS_AV, "PyAV is required for replay")
    @unittest.skipUnless(GOLDEN_CAPTURE.is_file(), "golden capture is unavailable")
    def test_replay_json_stats_stdout_is_pure_json(self) -> None:
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            return_code = cli_module.main(
                [
                    "replay",
                    "--file",
                    str(GOLDEN_CAPTURE),
                    "--headless",
                    "--json-stats",
                ]
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(return_code, 0)
        self.assertEqual(payload["decode"]["frames"], 105)
        self.assertEqual(payload["decoder"]["errors"], 0)

    def test_missing_config_is_reported_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing.yaml"
            with redirect_stdout(io.StringIO()):
                return_code = cli_module.main(["config", "--config", str(missing_path)])
        self.assertEqual(return_code, 1)

    def test_doctor_reports_usbfs_permission_failure(self) -> None:
        info = UsbDeviceInfo(
            backend="sysfs",
            vid=0x2CA3,
            pid=0x1020,
            sysfs_name="1-8",
            bus=1,
            address=24,
            usbfs_path=Path("/dev/bus/usb/001/024"),
            usbfs_exists=True,
            access_error="USB device node is not readable/writable",
        )
        result = DiscoveryResult(
            vid=0x2CA3,
            pid=0x1020,
            sysfs=(info,),
            usbfs_dir_exists=True,
        )
        output = io.StringIO()
        with (
            patch.object(cli_module, "discover_devices", return_value=result),
            redirect_stdout(output),
        ):
            return_code = cli_module.main(["doctor", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(return_code, 1)
        self.assertFalse(payload["usbfs_ok"])
        self.assertIn(
            "not readable/writable",
            payload["devices"]["sysfs"][0]["access_error"],
        )

    @unittest.skipUnless(_HAS_AV, "PyAV is required for pipeline tests")
    def test_recording_error_is_reported_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            blocker = Path(temp_dir) / "not_a_directory"
            blocker.write_text("x", encoding="utf-8")
            record_path = blocker / "capture.bin"
            errors = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(errors):
                return_code = cli_module.main(
                    ["stream", "--headless", "--record", str(record_path)]
                )

        self.assertEqual(return_code, 1)
        self.assertIn("error: cannot create recording files", errors.getvalue())
        self.assertIn(str(record_path), errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    @unittest.skipUnless(_HAS_AV, "PyAV is required for pipeline tests")
    def test_no_frames_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            capture_path = Path(temp_dir) / "no_irap.h265"
            capture_path.write_bytes(make_non_irap_chunk())
            config = AppConfig()
            config.output.preview = False
            source = FileSource(capture_path)
            arguments = Namespace(json_stats=True)

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                return_code = cli_module._run_pipeline(config, source, arguments)

        payload = json.loads(output.getvalue())
        self.assertEqual(return_code, 1)
        self.assertEqual(payload["decode"]["frames"], 0)
        self.assertEqual(payload["decoder"]["errors"], 0)


if __name__ == "__main__":
    unittest.main()
