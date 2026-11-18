"""Command-line interface for the VT13 USB video receiver."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import shutil
import sys
import time

from .config import (
    AppConfig,
    ConfigError,
    default_config_yaml,
    dump_config,
    load_config,
    to_dict,
    validate_config,
)
from .decoder import DependencyError
from .device import (
    DEFAULT_PID,
    DEFAULT_VID,
    DeviceError,
    discover_devices,
    udev_rule_text,
)
from .pipeline import RecordingError, VT13Stream
from .sources import FileSource, SourceError


def _int_arg(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid integer: {value!r}") from exc


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def _apply_overrides(cfg: AppConfig, args: argparse.Namespace) -> AppConfig:
    if getattr(args, "vid", None) is not None:
        cfg.device.vid = args.vid
    if getattr(args, "pid", None) is not None:
        cfg.device.pid = args.pid
    if getattr(args, "interface", None) is not None:
        cfg.device.interface = args.interface
    if getattr(args, "endpoint", None) is not None:
        cfg.device.endpoint = args.endpoint
    if getattr(args, "serial", None) is not None:
        cfg.device.serial = args.serial
    if getattr(args, "headless", False):
        cfg.output.preview = False
    if getattr(args, "no_preview", False):
        cfg.output.preview = False
    if getattr(args, "preview_width", None) is not None:
        cfg.output.preview_width = args.preview_width
    if getattr(args, "record", None) is not None:
        cfg.output.record = args.record.expanduser().resolve()
    if getattr(args, "save_first", None) is not None:
        cfg.output.save_first = args.save_first.expanduser().resolve()
    if getattr(args, "parameter_sets_file", None) is not None:
        cfg.decoder.parameter_sets_file = args.parameter_sets_file.expanduser().resolve()
    if getattr(args, "save_parameter_sets", None) is not None:
        cfg.decoder.save_parameter_sets = args.save_parameter_sets.expanduser().resolve()
    if getattr(args, "read_size", None) is not None:
        cfg.read.read_size = args.read_size
    if getattr(args, "timeout_ms", None) is not None:
        cfg.read.timeout_ms = args.timeout_ms
    if getattr(args, "stats_interval", None) is not None:
        cfg.output.stats_interval_s = args.stats_interval
    if getattr(args, "seconds", None) is not None:
        cfg.runtime.max_seconds = args.seconds
    if getattr(args, "log_level", None) is not None:
        cfg.output.log_level = args.log_level
    validate_config(cfg)
    return cfg


def _device_parser(subparsers: argparse._SubParsersAction, name: str, help_text: str):
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("--vid", type=_int_arg, default=None, help="USB vendor ID, e.g. 0x2ca3")
    parser.add_argument("--pid", type=_int_arg, default=None, help="USB product ID, e.g. 0x1020")
    parser.add_argument("--json", action="store_true", help="print JSON")
    return parser


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None, help="YAML configuration file")
    parser.add_argument("--seconds", type=float, default=None, help="stop after N seconds (0 = until EOF/forever)")
    parser.add_argument("--headless", action="store_true", help="do not open an OpenCV window")
    parser.add_argument("--no-preview", action="store_true", help="same as --headless")
    parser.add_argument("--preview-width", type=int, default=None, help="resize preview window width")
    parser.add_argument("--record", type=Path, default=None, help="write raw EP bytes to this file")
    parser.add_argument("--save-first", type=Path, default=None, help="save the first decoded BGR frame")
    parser.add_argument("--parameter-sets-file", type=Path, default=None, help="Annex-B file to prime VPS/SPS/PPS cache")
    parser.add_argument("--save-parameter-sets", type=Path, default=None, help="write complete VPS/SPS/PPS to this Annex-B file")
    parser.add_argument("--read-size", type=int, default=None, help="USB bulk read size")
    parser.add_argument("--timeout-ms", type=int, default=None, help="USB read timeout in milliseconds")
    parser.add_argument("--stats-interval", type=float, default=None, help="status print interval in seconds")
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR, CRITICAL")
    parser.add_argument("--json-stats", action="store_true", help="print final stats as JSON")


def _cmd_devices(args: argparse.Namespace) -> int:
    vid = args.vid if args.vid is not None else DEFAULT_VID
    pid = args.pid if args.pid is not None else DEFAULT_PID
    result = discover_devices(vid, pid)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.sysfs or result.pyusb else 1

    print(f"Looking for {vid:04x}:{pid:04x}")
    print(f"usbfs directory: /dev/bus/usb exists={result.usbfs_dir_exists}")
    if result.pyusb_error:
        print(f"PyUSB/libusb: {result.pyusb_error}")
    if not result.sysfs and not result.pyusb:
        print("No matching device found in sysfs or libusb.")
        return 1

    for info in result.sysfs:
        print(
            f"sysfs: {info.sysfs_name} {info.manufacturer or '?'} {info.product or '?'} "
            f"serial={info.serial or '?'} bus={info.bus} address={info.address} "
            f"usbfs={info.usbfs_path} exists={info.usbfs_exists}"
        )
        for iface in info.interfaces:
            endpoints = ", ".join(f"0x{ep:02x}" for ep in iface.endpoints) or "none"
            ttys = ", ".join(iface.tty) or "none"
            print(
                f"  interface {iface.number}: class={iface.class_code} "
                f"endpoints=[{endpoints}] driver={iface.driver_name or 'none'} tty=[{ttys}]"
            )
        if info.access_error:
            print(f"  warning: {info.access_error}")

    for info in result.pyusb:
        print(
            f"pyusb: bus={info.bus} address={info.address} serial={info.serial or '?'} "
            f"configuration={info.configuration}"
        )
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    return _cmd_devices(args)


def _display_frame(cv2, frame, width: int, title: str) -> bool:
    image = frame.image
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if width and image.shape[1] > width:
        scale = width / image.shape[1]
        image = cv2.resize(image, (width, max(2, round(image.shape[0] * scale))))
    cv2.imshow(title, image)
    key = cv2.waitKey(1) & 0xFF
    return key not in (ord("q"), 27)


def _run_pipeline(cfg: AppConfig, source, args: argparse.Namespace) -> int:
    _configure_logging(cfg.output.log_level)
    stream = VT13Stream(cfg, source=source)
    cv2 = None
    if cfg.output.preview:
        try:
            import cv2 as cv2_module

            cv2 = cv2_module
            cv2.namedWindow(cfg.output.window_title, cv2.WINDOW_NORMAL)
        except Exception as exc:
            print(f"Preview unavailable ({exc}); continuing headless.", file=sys.stderr)
            cfg.output.preview = False

    stream.start()
    started = time.monotonic()
    last_stats = started
    try:
        while stream.is_running:
            frame = stream.read_frame(0.2)
            if frame is not None and cv2 is not None:
                if not _display_frame(cv2, frame, cfg.output.preview_width, cfg.output.window_title):
                    break
            now = time.monotonic()
            if now - last_stats >= cfg.output.stats_interval_s:
                last_stats = now
                if args.json_stats:
                    print(stream.status_line(), file=sys.stderr, flush=True)
                else:
                    print(stream.status_line(), flush=True)
            if cfg.runtime.max_seconds > 0 and now - started >= cfg.runtime.max_seconds:
                break
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
    finally:
        stream.stop()
        stream.join(5.0)
        if cv2 is not None:
            cv2.destroyAllWindows()

    snapshot = stream.snapshot()
    if args.json_stats:
        print(json.dumps(snapshot, indent=2, default=str))
    else:
        print(stream.status_line(), flush=True)
        decode = snapshot["decode"]
        stream_stats = snapshot["stream"]
        print(
            f"final: {decode['frames']} frames, {decode['width']}x{decode['height']}, "
            f"{stream_stats['keyframe_starts']} keyframe starts, "
            f"{stream_stats['discontinuities']} discontinuities, "
            f"{snapshot['usb']['errors']} USB errors",
            flush=True,
        )
    if snapshot["decoder"].get("errors") or snapshot["decode"]["frames"] == 0:
        return 1
    return 0


def _cmd_stream(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    cfg = _apply_overrides(cfg, args)
    return _run_pipeline(cfg, None, args)


def _cmd_replay(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    cfg = _apply_overrides(cfg, args)
    if args.file is None:
        raise ConfigError("replay requires --file")
    cfg.output.preview = False if args.headless or args.no_preview else cfg.output.preview
    # Offline replay should not drop decoded frames just because it is faster than
    # the consumer; use backpressure instead of the live-stream "latest frame" policy.
    cfg.decoder.queue_size = max(256, cfg.decoder.queue_size)
    cfg.decoder.drop_oldest = False
    source = FileSource(
        args.file.expanduser().resolve(),
        read_size=cfg.read.read_size,
        times_path=args.times.expanduser().resolve() if args.times else None,
    )
    return _run_pipeline(cfg, source, args)


def _dependency_status() -> dict[str, object]:
    modules = ["usb", "av", "cv2", "numpy", "yaml"]
    result: dict[str, object] = {}
    for module in modules:
        try:
            imported = __import__(module)
            result[module] = {"ok": True, "version": getattr(imported, "__version__", "")}
        except Exception as exc:
            result[module] = {"ok": False, "error": repr(exc)}
    result["ffmpeg"] = shutil.which("ffmpeg")
    result["ffprobe"] = shutil.which("ffprobe")
    return result


def _cmd_doctor(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    result = discover_devices(cfg.device.vid, cfg.device.pid)
    deps = _dependency_status()
    devices = result.sysfs or result.pyusb
    usbfs_ok = bool(devices) and all(
        info.usbfs_exists and not info.access_error for info in devices
    )
    report = {
        "dependencies": deps,
        "devices": result.to_dict(),
        "usbfs_ok": usbfs_ok,
        "udev_rule": udev_rule_text(cfg.device.vid, cfg.device.pid).strip(),
        "config": to_dict(cfg),
    }
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print("Dependencies:")
        for name, info in deps.items():
            if isinstance(info, dict):
                print(f"  {name}: {'OK' if info['ok'] else 'MISSING'} {info.get('version', '')}")
            else:
                print(f"  {name}: {info or 'not found'}")
        print("Device:")
        if devices:
            for info in devices:
                print(
                    f"  {info.sysfs_name or 'pyusb'}: bus={info.bus} address={info.address} "
                    f"serial={info.serial or '?'} usbfs={info.usbfs_path} exists={info.usbfs_exists}"
                )
                if info.access_error:
                    print(f"  warning: {info.access_error}")
        else:
            print("  no matching device")
        if result.pyusb_error:
            print(f"  libusb error: {result.pyusb_error}")
        if not usbfs_ok:
            print("  warning: USB device node is unavailable or not accessible; live capture cannot run.")
        print("Suggested udev rule (install to /etc/udev/rules.d/99-vt13-video.rules):")
        print(f"  {report['udev_rule']}")
    return 0 if devices and usbfs_ok else 1


def _cmd_config(args: argparse.Namespace) -> int:
    if args.write_default is not None:
        path = args.write_default.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(default_config_yaml(), encoding="utf-8")
        print(f"wrote default configuration to {path}")
        return 0
    cfg = load_config(args.config)
    if args.json:
        print(json.dumps(to_dict(cfg), indent=2, default=str))
    else:
        print(dump_config(cfg), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vt13-video",
        description="VT13 USB Bulk IN -> HEVC -> BGR real-time receiver",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    devices = _device_parser(subparsers, "devices", "list matching VT13/C5 devices")
    devices.set_defaults(func=_cmd_devices)
    inspect = _device_parser(subparsers, "inspect", "inspect USB descriptors and endpoints")
    inspect.set_defaults(func=_cmd_inspect)

    stream = subparsers.add_parser("stream", help="live USB video stream")
    _add_runtime_args(stream)
    stream.add_argument("--vid", type=_int_arg, default=None)
    stream.add_argument("--pid", type=_int_arg, default=None)
    stream.add_argument("--interface", type=_int_arg, default=None)
    stream.add_argument("--endpoint", type=_int_arg, default=None)
    stream.add_argument("--serial", default=None)
    stream.set_defaults(func=_cmd_stream)

    replay = subparsers.add_parser("replay", help="decode a raw capture offline")
    _add_runtime_args(replay)
    replay.add_argument("--file", type=Path, required=True)
    replay.add_argument("--times", type=Path, default=None, help="optional .times.tsv read timeline")
    replay.set_defaults(func=_cmd_replay)

    doctor = subparsers.add_parser("doctor", help="check dependencies, device, and usbfs")
    doctor.add_argument("--config", type=Path, default=None)
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=_cmd_doctor)

    config = subparsers.add_parser("config", help="show or write configuration")
    config.add_argument("--config", type=Path, default=None)
    config.add_argument("--write-default", type=Path, default=None)
    config.add_argument("--json", action="store_true")
    config.set_defaults(func=_cmd_config)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ConfigError, DependencyError, DeviceError, RecordingError, SourceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
