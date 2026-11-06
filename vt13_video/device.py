"""VT13 device discovery and descriptor inspection.

Discovery deliberately has two layers:

* sysfs is always readable on Linux and tells us whether the C5 is present,
  which interfaces/endpoints exist, and whether the CDC ports are bound.
* PyUSB/libusb is required to actually open the vendor endpoint.  If usbfs is
  unavailable (for example in a restricted container), sysfs still gives a
  useful, actionable diagnosis instead of a generic "device not found".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
from typing import Any


DEFAULT_VID = 0x2CA3
DEFAULT_PID = 0x1020
SYSFS_USB = Path("/sys/bus/usb/devices")
USBFS_ROOT = Path("/dev/bus/usb")


class DeviceError(RuntimeError):
    """Base class for device discovery/open failures."""


class DeviceNotFound(DeviceError):
    pass


class DeviceBusy(DeviceError):
    pass


class DeviceAccessError(DeviceError):
    pass


class AmbiguousDevice(DeviceError):
    pass


@dataclass
class InterfaceInfo:
    number: int
    class_code: int | None = None
    subclass: int | None = None
    protocol: int | None = None
    endpoints: tuple[int, ...] = ()
    driver_name: str | None = None
    kernel_driver_active: bool = False
    tty: tuple[str, ...] = ()


@dataclass
class UsbDeviceInfo:
    backend: str
    vid: int
    pid: int
    sysfs_name: str | None = None
    sysfs_path: Path | None = None
    bus: int | None = None
    address: int | None = None
    manufacturer: str | None = None
    product: str | None = None
    serial: str | None = None
    speed_mbps: float | None = None
    version: str | None = None
    configuration: int | None = None
    interfaces: tuple[InterfaceInfo, ...] = ()
    usbfs_path: Path | None = None
    usbfs_exists: bool = False
    access_error: str | None = None
    pyusb_error: str | None = None

    @property
    def identity(self) -> str:
        parts = [f"{self.vid:04x}:{self.pid:04x}"]
        if self.bus is not None and self.address is not None:
            parts.append(f"bus {self.bus} address {self.address}")
        if self.serial:
            parts.append(f"serial {self.serial}")
        return ", ".join(parts)

    @property
    def serial_ports(self) -> tuple[str, ...]:
        ports: list[str] = []
        for iface in self.interfaces:
            ports.extend(iface.tty)
        return tuple(ports)

    def endpoint_available(self, interface: int, endpoint: int) -> bool:
        for iface in self.interfaces:
            if iface.number == interface:
                return endpoint in iface.endpoints
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "vid": f"0x{self.vid:04x}",
            "pid": f"0x{self.pid:04x}",
            "sysfs_name": self.sysfs_name,
            "sysfs_path": str(self.sysfs_path) if self.sysfs_path else None,
            "bus": self.bus,
            "address": self.address,
            "manufacturer": self.manufacturer,
            "product": self.product,
            "serial": self.serial,
            "speed_mbps": self.speed_mbps,
            "version": self.version,
            "configuration": self.configuration,
            "interfaces": [
                {
                    "number": iface.number,
                    "class": iface.class_code,
                    "subclass": iface.subclass,
                    "protocol": iface.protocol,
                    "endpoints": [f"0x{ep:02x}" for ep in iface.endpoints],
                    "driver": iface.driver_name,
                    "kernel_driver_active": iface.kernel_driver_active,
                    "tty": list(iface.tty),
                }
                for iface in self.interfaces
            ],
            "usbfs_path": str(self.usbfs_path) if self.usbfs_path else None,
            "usbfs_exists": self.usbfs_exists,
            "access_error": self.access_error,
            "pyusb_error": self.pyusb_error,
        }


@dataclass
class DiscoveryResult:
    vid: int
    pid: int
    sysfs: tuple[UsbDeviceInfo, ...] = ()
    pyusb: tuple[UsbDeviceInfo, ...] = ()
    pyusb_error: str | None = None
    usbfs_dir_exists: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "vid": f"0x{self.vid:04x}",
            "pid": f"0x{self.pid:04x}",
            "usbfs_dir_exists": self.usbfs_dir_exists,
            "pyusb_error": self.pyusb_error,
            "sysfs": [d.to_dict() for d in self.sysfs],
            "pyusb": [d.to_dict() for d in self.pyusb],
        }


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _read_int(path: Path, base: int = 10) -> int | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return int(text, base)
    except ValueError:
        return None


def _read_hex(path: Path) -> int | None:
    return _read_int(path, 16)


def _read_float(path: Path) -> float | None:
    text = _read_text(path)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _usbfs_access_error(path: Path) -> str | None:
    """Return an actionable diagnostic when the current user cannot open a node."""
    try:
        stat_result = path.stat()
    except OSError as exc:
        return f"cannot inspect USB device node {path}: {exc}"
    if os.access(path, os.R_OK | os.W_OK):
        return None
    return (
        f"USB device node {path} is not readable/writable by uid {os.geteuid()} "
        f"(mode={stat_result.st_mode & 0o7777:04o}, uid={stat_result.st_uid}, "
        f"gid={stat_result.st_gid}). Install udev/99-vt13-video.rules and reload "
        "udev, or grant this user access to the node."
    )


def _link_name(path: Path) -> str | None:
    try:
        target = os.readlink(path)
    except OSError:
        return None
    return Path(target).name


def _interface_paths(device_path: Path) -> list[Path]:
    """Locate interface directories for a USB device in sysfs.

    On the /sys/bus/usb/devices symlink tree, interface entries are siblings
    (``1-8:1.0``).  On a resolved device path they are children.  Support both
    layouts so discovery works whether the caller passes an entry or its target.
    """
    direct = sorted(device_path.glob(f"{device_path.name}:1.*"))
    if direct:
        return direct
    return sorted(device_path.parent.glob(f"{device_path.name}:1.*"))


def _interface_directory(device_path: Path, number: int) -> Path:
    direct = device_path / f"{device_path.name}:1.{number}"
    if direct.is_dir():
        return direct
    return device_path.parent / f"{device_path.name}:1.{number}"


def _interfaces_from_sysfs(device_path: Path) -> tuple[InterfaceInfo, ...]:
    interfaces: list[InterfaceInfo] = []
    for iface_path in _interface_paths(device_path):
        number = _read_int(iface_path / "bInterfaceNumber") or 0
        endpoints: list[int] = []
        for ep_path in sorted(iface_path.glob("ep_*")):
            ep = _read_hex(ep_path / "bEndpointAddress")
            if ep is not None:
                endpoints.append(ep)
        tty_dir = iface_path / "tty"
        ttys: list[str] = []
        if tty_dir.is_dir():
            try:
                ttys = sorted(p.name for p in tty_dir.iterdir())
            except OSError:
                ttys = []
        interfaces.append(
            InterfaceInfo(
                number=number,
                class_code=_read_hex(iface_path / "bInterfaceClass"),
                subclass=_read_hex(iface_path / "bInterfaceSubClass"),
                protocol=_read_hex(iface_path / "bInterfaceProtocol"),
                endpoints=tuple(endpoints),
                driver_name=_link_name(iface_path / "driver"),
                kernel_driver_active=(iface_path / "driver").exists(),
                tty=tuple(ttys),
            )
        )
    return tuple(interfaces)


_SYSFS_DEVICE_RE = re.compile(r"^\d+-\d+(?:\.\d+)*$")


def sysfs_devices(vid: int = DEFAULT_VID, pid: int = DEFAULT_PID) -> tuple[UsbDeviceInfo, ...]:
    """Return matching USB devices using only Linux sysfs."""
    devices: list[UsbDeviceInfo] = []
    if not SYSFS_USB.is_dir():
        return ()
    try:
        entries = list(SYSFS_USB.iterdir())
    except OSError:
        return ()
    for entry in entries:
        if not _SYSFS_DEVICE_RE.match(entry.name):
            continue
        if _read_hex(entry / "idVendor") != vid or _read_hex(entry / "idProduct") != pid:
            continue
        bus = _read_int(entry / "busnum")
        address = _read_int(entry / "devnum")
        usbfs_path = None
        if bus is not None and address is not None:
            usbfs_path = USBFS_ROOT / f"{bus:03d}" / f"{address:03d}"
        access_error = None
        usbfs_exists = bool(usbfs_path and usbfs_path.exists())
        if usbfs_path is not None:
            if not usbfs_exists:
                access_error = (
                    f"USB device node {usbfs_path} is missing. libusb cannot open the endpoint "
                    "without usbfs; check /dev/bus/usb and container device permissions."
                )
            else:
                access_error = _usbfs_access_error(usbfs_path)
        devices.append(
            UsbDeviceInfo(
                backend="sysfs",
                vid=vid,
                pid=pid,
                sysfs_name=entry.name,
                sysfs_path=entry.resolve(),
                bus=bus,
                address=address,
                manufacturer=_read_text(entry / "manufacturer"),
                product=_read_text(entry / "product"),
                serial=_read_text(entry / "serial"),
                speed_mbps=_read_float(entry / "speed"),
                version=_read_text(entry / "version"),
                configuration=_read_int(entry / "bConfigurationValue"),
                interfaces=_interfaces_from_sysfs(entry),
                usbfs_path=usbfs_path,
                usbfs_exists=usbfs_exists,
                access_error=access_error,
            )
        )
    return tuple(devices)


def _get_string(dev: Any, index: int | None) -> str | None:
    if not index:
        return None
    try:
        import usb.util

        return usb.util.get_string(dev, index)
    except Exception:
        return None


def pyusb_devices(vid: int = DEFAULT_VID, pid: int = DEFAULT_PID) -> tuple[tuple[UsbDeviceInfo, ...], str | None]:
    """Return matching USB devices through PyUSB, plus a diagnostic on failure."""
    try:
        import usb.core
    except ImportError as exc:
        return (), f"PyUSB is not installed: {exc}"
    try:
        found = list(usb.core.find(find_all=True, idVendor=vid, idProduct=pid))
    except Exception as exc:  # libusb initialization failures are backend-specific
        return (), f"libusb device enumeration failed: {exc!r}"

    devices: list[UsbDeviceInfo] = []
    for dev in found:
        bus = getattr(dev, "bus", None)
        address = getattr(dev, "address", None)
        sysfs_path_text = getattr(dev, "sysfs_path", None)
        sysfs_path = Path(sysfs_path_text) if sysfs_path_text else None
        usbfs_path = None
        if bus is not None and address is not None:
            usbfs_path = USBFS_ROOT / f"{bus:03d}" / f"{address:03d}"
        interfaces: list[InterfaceInfo] = []
        configuration = None
        try:
            config = dev.get_active_configuration()
            configuration = int(config.bConfigurationValue)
            for intf in config:
                number = int(intf.bInterfaceNumber)
                try:
                    kernel_active = bool(dev.is_kernel_driver_active(number))
                except Exception:
                    kernel_active = False
                ttys: list[str] = []
                if sysfs_path is not None:
                    tty_dir = _interface_directory(sysfs_path, number) / "tty"
                    if tty_dir.is_dir():
                        try:
                            ttys = sorted(p.name for p in tty_dir.iterdir())
                        except OSError:
                            ttys = []
                interfaces.append(
                    InterfaceInfo(
                        number=number,
                        class_code=int(intf.bInterfaceClass),
                        subclass=int(intf.bInterfaceSubClass),
                        protocol=int(intf.bInterfaceProtocol),
                        endpoints=tuple(int(ep.bEndpointAddress) for ep in intf),
                        kernel_driver_active=kernel_active,
                        tty=tuple(ttys),
                    )
                )
        except Exception as exc:
            interfaces = []
            configuration = None
            error = f"cannot read active configuration: {exc!r}"
        else:
            error = None
        devices.append(
            UsbDeviceInfo(
                backend="pyusb",
                vid=vid,
                pid=pid,
                sysfs_path=sysfs_path,
                bus=bus,
                address=address,
                manufacturer=_get_string(dev, getattr(dev, "iManufacturer", None)),
                product=_get_string(dev, getattr(dev, "iProduct", None)),
                serial=_get_string(dev, getattr(dev, "iSerialNumber", None)),
                configuration=configuration,
                interfaces=tuple(interfaces),
                usbfs_path=usbfs_path,
                usbfs_exists=bool(usbfs_path and usbfs_path.exists()),
                access_error=error,
            )
        )
    return tuple(devices), None


def discover_devices(vid: int = DEFAULT_VID, pid: int = DEFAULT_PID) -> DiscoveryResult:
    sysfs = sysfs_devices(vid, pid)
    pyusb, error = pyusb_devices(vid, pid)
    return DiscoveryResult(
        vid=vid,
        pid=pid,
        sysfs=sysfs,
        pyusb=pyusb,
        pyusb_error=error,
        usbfs_dir_exists=USBFS_ROOT.is_dir(),
    )


def find_device(vid: int = DEFAULT_VID, pid: int = DEFAULT_PID, serial: str | None = None) -> Any:
    """Find exactly one PyUSB device, with actionable errors."""
    try:
        import usb.core
    except ImportError as exc:
        raise DeviceAccessError(f"PyUSB is not installed: {exc}") from exc
    try:
        candidates = list(usb.core.find(find_all=True, idVendor=vid, idProduct=pid))
    except Exception as exc:
        raise DeviceAccessError(
            f"libusb cannot enumerate USB devices: {exc!r}. "
            "Check that /dev/bus/usb is available and the process has permission."
        ) from exc

    if not candidates:
        sysfs = sysfs_devices(vid, pid)
        if sysfs:
            info = sysfs[0]
            raise DeviceAccessError(
                f"{vid:04x}:{pid:04x} is visible in sysfs ({info.sysfs_name}) but libusb "
                f"cannot open it. {info.access_error or 'Check /dev/bus/usb and udev permissions.'}"
            )
        raise DeviceNotFound(
            f"USB device {vid:04x}:{pid:04x} not found. Check the cable, power, and lsusb."
        )

    if serial is not None:
        matches = []
        for dev in candidates:
            try:
                candidate_serial = dev.serial_number
            except Exception:
                candidate_serial = None
            if candidate_serial == serial:
                matches.append(dev)
        if not matches:
            raise DeviceNotFound(
                f"USB device {vid:04x}:{pid:04x} found, but no device has serial {serial!r}."
            )
        candidates = matches

    if len(candidates) > 1:
        raise AmbiguousDevice(
            f"Multiple {vid:04x}:{pid:04x} devices are connected. Set device.serial in the "
            "YAML configuration to select one."
        )
    return candidates[0]


def udev_rule_text(vid: int = DEFAULT_VID, pid: int = DEFAULT_PID) -> str:
    return (
        f'SUBSYSTEM=="usb", ATTR{{idVendor}}=="{vid:04x}", '
        f'ATTR{{idProduct}}=="{pid:04x}", TAG+="uaccess"\n'
    )


def usbfs_device_node(info: UsbDeviceInfo) -> Path | None:
    return info.usbfs_path
