"""YAML configuration for the VT13 USB video receiver."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping


class ConfigError(ValueError):
    """Raised when a configuration file is invalid or contains unknown keys."""


@dataclass
class DeviceConfig:
    vid: int = 0x2CA3
    pid: int = 0x1020
    interface: int = 0
    endpoint: int = 0x81
    serial: str | None = None
    detach_kernel_driver: bool = False
    status_interface: int | None = 1
    status_endpoint: int | None = 0x82
    status_drain: bool = True


@dataclass
class ReadConfig:
    read_size: int = 2048
    timeout_ms: int = 250
    stall_timeout_s: float = 3.0
    drain_reads: int = 2


@dataclass
class RecoveryConfig:
    enabled: bool = True
    initial_backoff_s: float = 0.25
    max_backoff_s: float = 5.0
    multiplier: float = 2.0
    jitter_fraction: float = 0.1
    healthy_reads: int = 50
    healthy_seconds: float = 5.0
    reset_after_failures: int = 0
    clear_halt_on_error: bool = True
    gap_threshold_s: float = 0.5
    reset_on_gap: bool = False
    kernel_abort_watch: bool = False


@dataclass
class ControlConfig:
    enabled: bool = False
    port: str | None = None
    iframe_on_connect: bool = True
    iframe_on_recovery: bool = True
    iframe_retry_s: float = 2.0
    min_iframe_interval_s: float = 0.5
    pairing_poll_s: float = 1.0


@dataclass
class DecoderConfig:
    codec: str = "hevc"
    backend: str = "pyav"
    ffmpeg_path: str | None = None
    ffmpeg_codec: str = "hevc_v4l2m2m"
    require_keyframe: bool = True
    allow_corrupt_frames: bool = True
    emit_corrupt_frames: bool = False
    parameter_sets_file: Path | None = None
    save_parameter_sets: Path | None = None
    max_consecutive_errors: int = 3
    queue_size: int = 8
    drop_oldest: bool = True
    output_format: str = "bgr24"
    convert_bgr: bool = True
    display: str = "none"
    display_width: int = 1024
    display_height: int = 576
    ffplay_path: str | None = None
    stall_restart_s: float = 0.0


@dataclass
class OutputConfig:
    preview: bool = True
    preview_width: int = 1000
    window_title: str = "VT13 USB HEVC"
    record: Path | None = None
    save_first: Path | None = None
    stats_interval_s: float = 1.0
    log_level: str = "INFO"


@dataclass
class RuntimeConfig:
    max_seconds: float = 0.0


@dataclass
class AppConfig:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    read: ReadConfig = field(default_factory=ReadConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    decoder: DecoderConfig = field(default_factory=DecoderConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    config_path: Path | None = None


_TOP_LEVEL_KEYS = {"device", "read", "recovery", "control", "decoder", "output", "runtime"}
_SECTION_KEYS = {
    "device": {f.name for f in fields(DeviceConfig)},
    "read": {f.name for f in fields(ReadConfig)},
    "recovery": {f.name for f in fields(RecoveryConfig)},
    "control": {f.name for f in fields(ControlConfig)},
    "decoder": {f.name for f in fields(DecoderConfig)},
    "output": {f.name for f in fields(OutputConfig)},
    "runtime": {f.name for f in fields(RuntimeConfig)},
}


def _section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name, {})
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} must be a mapping, got {type(value).__name__}")
    unknown = sorted(set(value) - _SECTION_KEYS[name])
    if unknown:
        raise ConfigError(f"unknown {name} key(s): {', '.join(unknown)}")
    return value


def _as_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be an integer, not a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ConfigError(f"{name} must be an integer, got {value!r}") from exc
    raise ConfigError(f"{name} must be an integer, got {type(value).__name__}")


def _as_optional_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    return _as_int(value, name)


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be a number, not a boolean")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{name} must be a number, got {value!r}") from exc


def _as_bool(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "on", "1"}:
            return True
        if lowered in {"false", "no", "off", "0"}:
            return False
    raise ConfigError(f"{name} must be a boolean, got {value!r}")


def _as_str(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{name} must be a string, got {type(value).__name__}")
    return value


def _as_optional_str(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _as_str(value, name)


def _as_path(value: Any, name: str, base_dir: Path) -> Path | None:
    if value is None:
        return None
    text = _as_str(value, name)
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _device_from(data: Mapping[str, Any]) -> DeviceConfig:
    section = _section(data, "device")
    cfg = DeviceConfig()
    if "vid" in section:
        cfg.vid = _as_int(section["vid"], "device.vid")
    if "pid" in section:
        cfg.pid = _as_int(section["pid"], "device.pid")
    if "interface" in section:
        cfg.interface = _as_int(section["interface"], "device.interface")
    if "endpoint" in section:
        cfg.endpoint = _as_int(section["endpoint"], "device.endpoint")
    if "serial" in section:
        cfg.serial = _as_optional_str(section["serial"], "device.serial")
    if "detach_kernel_driver" in section:
        cfg.detach_kernel_driver = _as_bool(
            section["detach_kernel_driver"], "device.detach_kernel_driver"
        )
    if "status_interface" in section:
        cfg.status_interface = _as_optional_int(
            section["status_interface"], "device.status_interface"
        )
    if "status_endpoint" in section:
        cfg.status_endpoint = _as_optional_int(
            section["status_endpoint"], "device.status_endpoint"
        )
    if "status_drain" in section:
        cfg.status_drain = _as_bool(section["status_drain"], "device.status_drain")
    return cfg


def _read_from(data: Mapping[str, Any]) -> ReadConfig:
    section = _section(data, "read")
    cfg = ReadConfig()
    if "read_size" in section:
        cfg.read_size = _as_int(section["read_size"], "read.read_size")
    if "timeout_ms" in section:
        cfg.timeout_ms = _as_int(section["timeout_ms"], "read.timeout_ms")
    if "stall_timeout_s" in section:
        cfg.stall_timeout_s = _as_float(section["stall_timeout_s"], "read.stall_timeout_s")
    if "drain_reads" in section:
        cfg.drain_reads = _as_int(section["drain_reads"], "read.drain_reads")
    return cfg


def _recovery_from(data: Mapping[str, Any]) -> RecoveryConfig:
    section = _section(data, "recovery")
    cfg = RecoveryConfig()
    for key in (
        "initial_backoff_s",
        "max_backoff_s",
        "multiplier",
        "jitter_fraction",
        "healthy_seconds",
        "gap_threshold_s",
    ):
        if key in section:
            setattr(cfg, key, _as_float(section[key], f"recovery.{key}"))
    for key in ("enabled", "clear_halt_on_error", "reset_on_gap", "kernel_abort_watch"):
        if key in section:
            setattr(cfg, key, _as_bool(section[key], f"recovery.{key}"))
    for key in ("healthy_reads", "reset_after_failures"):
        if key in section:
            setattr(cfg, key, _as_int(section[key], f"recovery.{key}"))
    return cfg


def _control_from(data: Mapping[str, Any]) -> ControlConfig:
    section = _section(data, "control")
    cfg = ControlConfig()
    if "enabled" in section:
        cfg.enabled = _as_bool(section["enabled"], "control.enabled")
    if "port" in section:
        cfg.port = _as_optional_str(section["port"], "control.port")
    for key in ("iframe_on_connect", "iframe_on_recovery"):
        if key in section:
            setattr(cfg, key, _as_bool(section[key], f"control.{key}"))
    for key in ("iframe_retry_s", "min_iframe_interval_s", "pairing_poll_s"):
        if key in section:
            setattr(cfg, key, _as_float(section[key], f"control.{key}"))
    return cfg


def _decoder_from(data: Mapping[str, Any], base_dir: Path) -> DecoderConfig:
    section = _section(data, "decoder")
    cfg = DecoderConfig()
    if "codec" in section:
        cfg.codec = _as_str(section["codec"], "decoder.codec")
    if "backend" in section:
        cfg.backend = _as_str(section["backend"], "decoder.backend")
    if "ffmpeg_path" in section:
        cfg.ffmpeg_path = _as_optional_str(section["ffmpeg_path"], "decoder.ffmpeg_path")
    if "ffmpeg_codec" in section:
        cfg.ffmpeg_codec = _as_str(section["ffmpeg_codec"], "decoder.ffmpeg_codec")
    if "require_keyframe" in section:
        cfg.require_keyframe = _as_bool(section["require_keyframe"], "decoder.require_keyframe")
    if "allow_corrupt_frames" in section:
        cfg.allow_corrupt_frames = _as_bool(
            section["allow_corrupt_frames"], "decoder.allow_corrupt_frames"
        )
    if "emit_corrupt_frames" in section:
        cfg.emit_corrupt_frames = _as_bool(
            section["emit_corrupt_frames"], "decoder.emit_corrupt_frames"
        )
    if "parameter_sets_file" in section:
        cfg.parameter_sets_file = _as_path(
            section["parameter_sets_file"], "decoder.parameter_sets_file", base_dir
        )
    if "save_parameter_sets" in section:
        cfg.save_parameter_sets = _as_path(
            section["save_parameter_sets"], "decoder.save_parameter_sets", base_dir
        )
    if "max_consecutive_errors" in section:
        cfg.max_consecutive_errors = _as_int(
            section["max_consecutive_errors"], "decoder.max_consecutive_errors"
        )
    if "queue_size" in section:
        cfg.queue_size = _as_int(section["queue_size"], "decoder.queue_size")
    if "drop_oldest" in section:
        cfg.drop_oldest = _as_bool(section["drop_oldest"], "decoder.drop_oldest")
    if "output_format" in section:
        cfg.output_format = _as_str(section["output_format"], "decoder.output_format")
    if "convert_bgr" in section:
        cfg.convert_bgr = _as_bool(section["convert_bgr"], "decoder.convert_bgr")
    if "display" in section:
        cfg.display = _as_str(section["display"], "decoder.display")
    if "display_width" in section:
        cfg.display_width = _as_int(section["display_width"], "decoder.display_width")
    if "display_height" in section:
        cfg.display_height = _as_int(section["display_height"], "decoder.display_height")
    if "ffplay_path" in section:
        cfg.ffplay_path = _as_optional_str(section["ffplay_path"], "decoder.ffplay_path")
    if "stall_restart_s" in section:
        cfg.stall_restart_s = _as_float(section["stall_restart_s"], "decoder.stall_restart_s")
    return cfg


def _output_from(data: Mapping[str, Any], base_dir: Path) -> OutputConfig:
    section = _section(data, "output")
    cfg = OutputConfig()
    if "preview" in section:
        cfg.preview = _as_bool(section["preview"], "output.preview")
    if "preview_width" in section:
        cfg.preview_width = _as_int(section["preview_width"], "output.preview_width")
    if "window_title" in section:
        cfg.window_title = _as_str(section["window_title"], "output.window_title")
    if "record" in section:
        cfg.record = _as_path(section["record"], "output.record", base_dir)
    if "save_first" in section:
        cfg.save_first = _as_path(section["save_first"], "output.save_first", base_dir)
    if "stats_interval_s" in section:
        cfg.stats_interval_s = _as_float(section["stats_interval_s"], "output.stats_interval_s")
    if "log_level" in section:
        cfg.log_level = _as_str(section["log_level"], "output.log_level")
    return cfg


def _runtime_from(data: Mapping[str, Any]) -> RuntimeConfig:
    section = _section(data, "runtime")
    cfg = RuntimeConfig()
    if "max_seconds" in section:
        cfg.max_seconds = _as_float(section["max_seconds"], "runtime.max_seconds")
    return cfg


def from_dict(data: Mapping[str, Any] | None, base_dir: Path | None = None) -> AppConfig:
    """Build an AppConfig from a YAML-style mapping.

    Relative paths are resolved against ``base_dir`` (normally the directory
    containing the YAML file).
    """
    if data is None:
        data = {}
    if not isinstance(data, Mapping):
        raise ConfigError(f"configuration root must be a mapping, got {type(data).__name__}")
    unknown = sorted(set(data) - _TOP_LEVEL_KEYS)
    if unknown:
        raise ConfigError(f"unknown top-level key(s): {', '.join(unknown)}")
    base = (base_dir or Path.cwd()).expanduser().resolve()
    cfg = AppConfig(
        device=_device_from(data),
        read=_read_from(data),
        recovery=_recovery_from(data),
        control=_control_from(data),
        decoder=_decoder_from(data, base),
        output=_output_from(data, base),
        runtime=_runtime_from(data),
    )
    validate_config(cfg)
    return cfg


def validate_config(cfg: AppConfig) -> None:
    if not 0 <= cfg.device.vid <= 0xFFFF:
        raise ConfigError("device.vid must be between 0x0000 and 0xFFFF")
    if not 0 <= cfg.device.pid <= 0xFFFF:
        raise ConfigError("device.pid must be between 0x0000 and 0xFFFF")
    if not 0 <= cfg.device.interface <= 255:
        raise ConfigError("device.interface must be between 0 and 255")
    if not 0x01 <= cfg.device.endpoint <= 0xFF:
        raise ConfigError("device.endpoint must be between 0x01 and 0xFF")
    if not (cfg.device.endpoint & 0x80):
        raise ConfigError("device.endpoint must be an IN endpoint (bit 7 set)")
    if cfg.device.serial is not None and not cfg.device.serial.strip():
        raise ConfigError("device.serial must be non-empty when set")
    if cfg.device.status_drain:
        if cfg.device.status_interface is None or cfg.device.status_endpoint is None:
            raise ConfigError(
                "device.status_interface and device.status_endpoint must be set "
                "when device.status_drain is true"
            )
        if not 0 <= cfg.device.status_interface <= 255:
            raise ConfigError("device.status_interface must be between 0 and 255")
        if not 0x01 <= cfg.device.status_endpoint <= 0xFF:
            raise ConfigError("device.status_endpoint must be between 0x01 and 0xFF")
        if not (cfg.device.status_endpoint & 0x80):
            raise ConfigError("device.status_endpoint must be an IN endpoint (bit 7 set)")
        if cfg.device.status_interface == cfg.device.interface:
            raise ConfigError("device.status_interface must differ from device.interface")

    if not 64 <= cfg.read.read_size <= 4 * 1024 * 1024:
        raise ConfigError("read.read_size must be between 64 and 4 MiB")
    if not 1 <= cfg.read.timeout_ms <= 60_000:
        raise ConfigError("read.timeout_ms must be between 1 and 60000")
    if cfg.read.stall_timeout_s <= 0:
        raise ConfigError("read.stall_timeout_s must be positive")
    if cfg.read.drain_reads < 0:
        raise ConfigError("read.drain_reads must be zero or positive")

    if cfg.recovery.initial_backoff_s < 0:
        raise ConfigError("recovery.initial_backoff_s must be zero or positive")
    if cfg.recovery.max_backoff_s < cfg.recovery.initial_backoff_s:
        raise ConfigError("recovery.max_backoff_s must be >= initial_backoff_s")
    if cfg.recovery.multiplier < 1.0:
        raise ConfigError("recovery.multiplier must be >= 1.0")
    if not 0.0 <= cfg.recovery.jitter_fraction <= 1.0:
        raise ConfigError("recovery.jitter_fraction must be between 0 and 1")
    if cfg.recovery.healthy_reads < 1:
        raise ConfigError("recovery.healthy_reads must be at least 1")
    if cfg.recovery.healthy_seconds <= 0:
        raise ConfigError("recovery.healthy_seconds must be positive")
    if cfg.recovery.reset_after_failures < 0:
        raise ConfigError("recovery.reset_after_failures must be zero or positive")
    if cfg.recovery.gap_threshold_s < 0:
        raise ConfigError("recovery.gap_threshold_s must be zero or positive")

    if cfg.control.port is not None and not cfg.control.port.strip():
        raise ConfigError("control.port must be non-empty when set")
    if cfg.control.iframe_retry_s < 0:
        raise ConfigError("control.iframe_retry_s must be zero or positive")
    if cfg.control.min_iframe_interval_s < 0:
        raise ConfigError("control.min_iframe_interval_s must be zero or positive")
    if cfg.control.pairing_poll_s < 0:
        raise ConfigError("control.pairing_poll_s must be zero or positive")

    if cfg.decoder.backend not in {"pyav", "ffmpeg-pipe"}:
        raise ConfigError("decoder.backend must be 'pyav' or 'ffmpeg-pipe'")
    if cfg.decoder.backend == "pyav" and cfg.decoder.codec.lower() not in {"hevc", "h265", "hevc_v4l2m2m"}:
        raise ConfigError("decoder.codec supports 'hevc', 'h265', or 'hevc_v4l2m2m'")
    if not cfg.decoder.ffmpeg_codec.strip():
        raise ConfigError("decoder.ffmpeg_codec must be non-empty")
    if cfg.decoder.emit_corrupt_frames and not cfg.decoder.allow_corrupt_frames:
        raise ConfigError(
            "decoder.emit_corrupt_frames requires decoder.allow_corrupt_frames=true"
        )
    if cfg.decoder.max_consecutive_errors < 1:
        raise ConfigError("decoder.max_consecutive_errors must be at least 1")
    if cfg.decoder.queue_size < 1:
        raise ConfigError("decoder.queue_size must be at least 1")
    if cfg.decoder.output_format not in {"bgr24", "rgb24", "gray"}:
        raise ConfigError("decoder.output_format must be bgr24, rgb24, or gray")
    if cfg.decoder.display not in {"none", "ffplay"}:
        raise ConfigError("decoder.display must be 'none' or 'ffplay'")
    if cfg.decoder.display_width < 16 or cfg.decoder.display_height < 16:
        raise ConfigError("decoder.display_width/display_height must be at least 16")
    if cfg.decoder.stall_restart_s < 0:
        raise ConfigError("decoder.stall_restart_s must be zero or positive")
    if cfg.decoder.parameter_sets_file is not None and not cfg.decoder.parameter_sets_file.is_file():
        raise ConfigError(
            f"decoder.parameter_sets_file does not exist: {cfg.decoder.parameter_sets_file}"
        )
    if (
        cfg.decoder.save_parameter_sets is not None
        and cfg.decoder.save_parameter_sets.exists()
        and cfg.decoder.save_parameter_sets.is_dir()
    ):
        raise ConfigError(
            f"decoder.save_parameter_sets is a directory: {cfg.decoder.save_parameter_sets}"
        )

    if cfg.output.preview_width < 16:
        raise ConfigError("output.preview_width must be at least 16")
    if cfg.output.stats_interval_s <= 0:
        raise ConfigError("output.stats_interval_s must be positive")
    if cfg.output.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError("output.log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")

    if cfg.runtime.max_seconds < 0:
        raise ConfigError("runtime.max_seconds must be zero or positive")


def load_config(path: Path | str | None = None) -> AppConfig:
    """Load and validate a YAML configuration file.

    With no path, defaults are returned.  Relative paths inside the YAML are
    resolved relative to that YAML file, not the process working directory.
    """
    if path is None:
        cfg = AppConfig()
        validate_config(cfg)
        return cfg

    import yaml  # imported lazily so device discovery works without PyYAML

    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise ConfigError(f"configuration file not found: {config_path}")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"cannot parse YAML {config_path}: {exc}") from exc
    cfg = from_dict(data, config_path.resolve().parent)
    cfg.config_path = config_path.resolve()
    return cfg


def _serializable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            f.name: _serializable(getattr(value, f.name))
            for f in fields(value)
            if f.name != "config_path"
        }
    return value


def to_dict(cfg: AppConfig) -> dict[str, Any]:
    return _serializable(cfg)


def dump_config(cfg: AppConfig) -> str:
    import yaml

    return yaml.safe_dump(to_dict(cfg), sort_keys=False)


def default_config_yaml() -> str:
    return dump_config(AppConfig())
