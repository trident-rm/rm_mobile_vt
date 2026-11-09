from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import yaml

from vt13_video.config import (
    ConfigError,
    default_config_yaml,
    from_dict,
    load_config,
    to_dict,
)


class ConfigTests(unittest.TestCase):
    def test_relative_paths_resolve_from_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            parameter_file = base / "params.h265"
            parameter_file.write_bytes(b"\x00\x00\x01\x40\x01")
            config_path = base / "vt13.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "device:",
                        "  vid: 0x2ca3",
                        "  pid: 0x1020",
                        "  endpoint: 0x81",
                        "read:",
                        "  read_size: 32768",
                        "  timeout_ms: 500",
                        "recovery:",
                        "  clear_halt_on_error: true",
                        "  reset_on_gap: false",
                        "decoder:",
                        "  parameter_sets_file: params.h265",
                        "  save_parameter_sets: params/saved.h265",
                        "output:",
                        "  preview: false",
                        "  record: records/raw.h265",
                        "  save_first: frames/first.png",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

            self.assertEqual(config.device.vid, 0x2CA3)
            self.assertEqual(config.device.pid, 0x1020)
            self.assertEqual(config.read.read_size, 32768)
            self.assertTrue(config.recovery.clear_halt_on_error)
            self.assertFalse(config.recovery.reset_on_gap)
            self.assertTrue(config.device.status_drain)
            self.assertEqual(config.device.status_interface, 1)
            self.assertEqual(config.device.status_endpoint, 0x82)
            self.assertEqual(config.decoder.parameter_sets_file, parameter_file.resolve())
            self.assertEqual(
                config.decoder.save_parameter_sets,
                (base / "params" / "saved.h265").resolve(),
            )
            self.assertEqual(config.output.record, (base / "records" / "raw.h265").resolve())
            self.assertEqual(config.output.save_first, (base / "frames" / "first.png").resolve())
            self.assertEqual(config.config_path, config_path.resolve())

    def test_unknown_keys_are_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "unknown top-level"):
            from_dict({"video": {}})
        with self.assertRaisesRegex(ConfigError, "unknown decoder"):
            from_dict({"decoder": {"mystery": 1}})

    def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "IN endpoint"):
            from_dict({"device": {"endpoint": 0x01}})
        with self.assertRaisesRegex(ConfigError, "device.vid"):
            from_dict({"device": {"vid": 0x10000}})
        with self.assertRaisesRegex(ConfigError, "must be a boolean"):
            from_dict({"decoder": {"require_keyframe": 1}})
        with self.assertRaisesRegex(ConfigError, "read_size"):
            from_dict({"read": {"read_size": 8}})
        with self.assertRaisesRegex(ConfigError, "max_backoff_s"):
            from_dict(
                {
                    "recovery": {
                        "initial_backoff_s": 2.0,
                        "max_backoff_s": 1.0,
                    }
                }
            )

    def test_default_yaml_round_trip(self) -> None:
        data = yaml.safe_load(default_config_yaml())
        config = from_dict(data)

        self.assertEqual(config.device.vid, 0x2CA3)
        self.assertEqual(config.device.pid, 0x1020)
        self.assertEqual(config.device.endpoint, 0x81)
        self.assertEqual(config.read.read_size, 2048)
        self.assertTrue(config.recovery.clear_halt_on_error)
        self.assertFalse(config.recovery.reset_on_gap)
        self.assertTrue(config.device.status_drain)
        self.assertEqual(config.device.status_interface, 1)
        self.assertEqual(config.device.status_endpoint, 0x82)
        self.assertTrue(config.decoder.allow_corrupt_frames)
        self.assertFalse(config.decoder.emit_corrupt_frames)
        self.assertIsNone(config.decoder.save_parameter_sets)
        self.assertTrue(config.output.preview)
        self.assertEqual(to_dict(config)["device"]["endpoint"], 0x81)

    def test_missing_config_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.yaml"
            with self.assertRaisesRegex(ConfigError, "not found"):
                load_config(missing)

    def test_defaults_without_a_file(self) -> None:
        config = load_config(None)
        self.assertIsNone(config.config_path)
        self.assertEqual(config.decoder.output_format, "bgr24")
        self.assertTrue(config.decoder.allow_corrupt_frames)
        self.assertFalse(config.decoder.emit_corrupt_frames)
        self.assertEqual(config.read.read_size, 2048)
        self.assertTrue(config.device.status_drain)

    def test_emit_corrupt_frames_requires_corrupt_output(self) -> None:
        with self.assertRaisesRegex(ConfigError, "emit_corrupt_frames"):
            from_dict(
                {
                    "decoder": {
                        "allow_corrupt_frames": False,
                        "emit_corrupt_frames": True,
                    }
                }
            )

    def test_v4l2m2m_codec_is_accepted(self) -> None:
        config = from_dict({"decoder": {"codec": "hevc_v4l2m2m"}})
        self.assertEqual(config.decoder.codec, "hevc_v4l2m2m")

    def test_unknown_codec_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "decoder.codec"):
            from_dict({"decoder": {"codec": "h264"}})

    def test_backend_default_and_validation(self) -> None:
        self.assertEqual(from_dict({}).decoder.backend, "pyav")
        config = from_dict({"decoder": {"backend": "ffmpeg-pipe", "ffmpeg_codec": "hevc"}})
        self.assertEqual(config.decoder.backend, "ffmpeg-pipe")
        self.assertEqual(config.decoder.ffmpeg_codec, "hevc")
        with self.assertRaisesRegex(ConfigError, "decoder.backend"):
            from_dict({"decoder": {"backend": "bogus"}})
        with self.assertRaisesRegex(ConfigError, "ffmpeg_codec"):
            from_dict({"decoder": {"ffmpeg_codec": "  "}})

    def test_display_config_validation(self) -> None:
        self.assertEqual(from_dict({}).decoder.display, "none")
        config = from_dict({"decoder": {"display": "ffplay", "display_width": 1024, "display_height": 576}})
        self.assertEqual(config.decoder.display, "ffplay")
        self.assertEqual(config.decoder.display_width, 1024)
        with self.assertRaisesRegex(ConfigError, "decoder.display"):
            from_dict({"decoder": {"display": "sdl"}})
        with self.assertRaisesRegex(ConfigError, "display_width"):
            from_dict({"decoder": {"display_width": 8}})

    def test_save_parameter_sets_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "parameter_sets"
            target.mkdir()
            with self.assertRaisesRegex(ConfigError, "is a directory"):
                from_dict({"decoder": {"save_parameter_sets": str(target)}})

    def test_kernel_abort_watch_can_be_enabled(self) -> None:
        self.assertTrue(from_dict({"recovery": {"kernel_abort_watch": True}}).recovery.kernel_abort_watch)

    def test_convert_bgr_can_be_disabled(self) -> None:
        self.assertFalse(from_dict({"decoder": {"convert_bgr": False}}).decoder.convert_bgr)

    def test_control_config_and_stall_watchdog(self) -> None:
        default = from_dict({})
        self.assertFalse(default.control.enabled)
        self.assertTrue(default.control.iframe_on_connect)
        self.assertTrue(default.control.iframe_on_recovery)
        self.assertEqual(default.decoder.stall_restart_s, 0.0)

        config = from_dict(
            {
                "control": {
                    "enabled": True,
                    "port": "/dev/ttyACM0",
                    "iframe_retry_s": 3,
                    "pairing_poll_s": 0,
                },
                "decoder": {"stall_restart_s": 5},
            }
        )
        self.assertTrue(config.control.enabled)
        self.assertEqual(config.control.port, "/dev/ttyACM0")
        self.assertEqual(config.control.iframe_retry_s, 3.0)
        self.assertEqual(config.control.pairing_poll_s, 0.0)
        self.assertEqual(config.decoder.stall_restart_s, 5.0)

    def test_control_negative_timers_are_rejected(self) -> None:
        for key in ("iframe_retry_s", "min_iframe_interval_s", "pairing_poll_s"):
            with self.assertRaisesRegex(ConfigError, f"control.{key}"):
                from_dict({"control": {key: -1}})
        with self.assertRaisesRegex(ConfigError, "stall_restart_s"):
            from_dict({"decoder": {"stall_restart_s": -1}})
        with self.assertRaisesRegex(ConfigError, "control.port"):
            from_dict({"control": {"port": "  "}})


if __name__ == "__main__":
    unittest.main()
