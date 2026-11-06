from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import vt13_video.device as device_module


class SysfsDiscoveryTests(unittest.TestCase):
    def _write_attribute(self, directory: Path, name: str, value: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / name).write_text(f"{value}\n", encoding="utf-8")

    def _make_fake_sysfs(self, base: Path) -> tuple[Path, Path]:
        sysfs_root = base / "sys"
        device_path = sysfs_root / "1-8"
        self._write_attribute(device_path, "idVendor", "2ca3")
        self._write_attribute(device_path, "idProduct", "1020")
        self._write_attribute(device_path, "busnum", "1")
        self._write_attribute(device_path, "devnum", "24")
        self._write_attribute(device_path, "manufacturer", "DJI Technology Co., Ltd.")
        self._write_attribute(device_path, "product", "C5")
        self._write_attribute(device_path, "serial", "123456789abcdef")
        self._write_attribute(device_path, "speed", "480")
        self._write_attribute(device_path, "version", "2.00")
        self._write_attribute(device_path, "bConfigurationValue", "1")

        interface_zero = sysfs_root / "1-8:1.0"
        self._write_attribute(interface_zero, "bInterfaceNumber", "0")
        self._write_attribute(interface_zero, "bInterfaceClass", "ff")
        self._write_attribute(interface_zero, "bInterfaceSubClass", "00")
        self._write_attribute(interface_zero, "bInterfaceProtocol", "00")
        endpoint_in = interface_zero / "ep_81"
        self._write_attribute(endpoint_in, "bEndpointAddress", "81")

        interface_one = sysfs_root / "1-8:1.1"
        self._write_attribute(interface_one, "bInterfaceNumber", "1")
        self._write_attribute(interface_one, "bInterfaceClass", "02")
        self._write_attribute(interface_one, "bInterfaceSubClass", "02")
        self._write_attribute(interface_one, "bInterfaceProtocol", "01")
        endpoint_status = interface_one / "ep_82"
        self._write_attribute(endpoint_status, "bEndpointAddress", "82")
        (interface_one / "tty" / "ttyACM0").mkdir(parents=True)

        driver_target = base / "fake_driver"
        driver_target.mkdir()
        (interface_zero / "driver").symlink_to(driver_target, target_is_directory=True)

        usbfs_root = base / "usbfs"
        usbfs_node = usbfs_root / "001" / "024"
        usbfs_node.parent.mkdir(parents=True)
        usbfs_node.write_bytes(b"")
        return sysfs_root, usbfs_root

    def test_sysfs_discovery_reads_device_and_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            sysfs_root, usbfs_root = self._make_fake_sysfs(base)
            with (
                patch.object(device_module, "SYSFS_USB", sysfs_root),
                patch.object(device_module, "USBFS_ROOT", usbfs_root),
            ):
                devices = device_module.sysfs_devices(0x2CA3, 0x1020)

            self.assertEqual(len(devices), 1)
            info = devices[0]
            self.assertEqual(info.sysfs_name, "1-8")
            self.assertEqual(info.bus, 1)
            self.assertEqual(info.address, 24)
            self.assertEqual(info.serial, "123456789abcdef")
            self.assertEqual(info.product, "C5")
            self.assertEqual(info.speed_mbps, 480.0)
            self.assertTrue(info.usbfs_exists)
            self.assertIsNone(info.access_error)
            self.assertEqual([interface.number for interface in info.interfaces], [0, 1])

            interface_zero = info.interfaces[0]
            self.assertEqual(interface_zero.class_code, 0xFF)
            self.assertEqual(interface_zero.endpoints, (0x81,))
            self.assertEqual(interface_zero.driver_name, "fake_driver")
            self.assertTrue(interface_zero.kernel_driver_active)
            self.assertTrue(info.endpoint_available(0, 0x81))
            self.assertFalse(info.endpoint_available(0, 0x82))

            interface_one = info.interfaces[1]
            self.assertEqual(interface_one.endpoints, (0x82,))
            self.assertEqual(interface_one.tty, ("ttyACM0",))
            self.assertEqual(info.serial_ports, ("ttyACM0",))

    def test_missing_usbfs_node_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            sysfs_root, _ = self._make_fake_sysfs(base)
            missing_usbfs_root = base / "missing_usbfs"
            with (
                patch.object(device_module, "SYSFS_USB", sysfs_root),
                patch.object(device_module, "USBFS_ROOT", missing_usbfs_root),
            ):
                devices = device_module.sysfs_devices(0x2CA3, 0x1020)

            self.assertEqual(len(devices), 1)
            self.assertFalse(devices[0].usbfs_exists)
            self.assertIn("is missing", devices[0].access_error or "")

    def test_usbfs_permission_denied_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            sysfs_root, usbfs_root = self._make_fake_sysfs(base)
            with (
                patch.object(device_module, "SYSFS_USB", sysfs_root),
                patch.object(device_module, "USBFS_ROOT", usbfs_root),
                patch.object(device_module.os, "access", return_value=False),
            ):
                devices = device_module.sysfs_devices(0x2CA3, 0x1020)

            self.assertEqual(len(devices), 1)
            self.assertTrue(devices[0].usbfs_exists)
            error = devices[0].access_error or ""
            self.assertIn("not readable/writable", error)
            self.assertIn("99-vt13-video.rules", error)

    def test_udev_rule_uses_uaccess(self) -> None:
        rule = device_module.udev_rule_text(0x2CA3, 0x1020)
        self.assertIn('ATTR{idVendor}=="2ca3"', rule)
        self.assertIn('ATTR{idProduct}=="1020"', rule)
        self.assertIn('TAG+="uaccess"', rule)


if __name__ == "__main__":
    unittest.main()
