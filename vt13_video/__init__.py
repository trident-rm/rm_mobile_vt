"""VT13 USB HEVC real-time receiver.

OpenCV is imported before PyAV so its Qt GUI backend initializes cleanly in
environments where PyAV's FFmpeg libraries are also loaded.
"""

try:
    import cv2 as _cv2  # noqa: F401
except ImportError:
    _cv2 = None

from .config import AppConfig, ConfigError, load_config
from .decoder import Frame, FrameQueue, HevcDecoder
from .device import DiscoveryResult, UsbDeviceInfo, discover_devices, find_device
from .nal import AccessUnit, AccessUnitAssembler, AnnexBParser, ParameterSetCache
from .pipeline import RecordingError, VT13Stream
from .sources import FileSource, VT13UsbSource

__version__ = "0.1.0"

__all__ = [
    "AccessUnit",
    "AccessUnitAssembler",
    "AnnexBParser",
    "AppConfig",
    "ConfigError",
    "DiscoveryResult",
    "FileSource",
    "Frame",
    "FrameQueue",
    "HevcDecoder",
    "ParameterSetCache",
    "RecordingError",
    "UsbDeviceInfo",
    "VT13Stream",
    "VT13UsbSource",
    "discover_devices",
    "find_device",
    "load_config",
]
