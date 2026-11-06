
import time
import usb.core
import usb.util

VID = 0x2CA3
PID = 0x1020

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    raise RuntimeError("DJI C5 not found")
print("Found DJI C5:", dev)

cfg = dev.get_active_configuration()
print("Configuration:", cfg.bConfigurationValue)

targets = [(0, 0x81), (1, 0x82)]

for iface, ep in targets:
    print(f"\nInterface {iface}, EP 0x{ep:02X}")

    if dev.is_kernel_driver_active(iface):
        print("Kernel driver active, skipped")
        continue

    claimed = False
    try:
        usb.util.claim_interface(dev, iface)
        claimed = True

        for i in range(5):
            t0 = time.monotonic()

            try:
                data = bytes(dev.read(
                    ep, 4096, timeout=1000
                ))

                elapsed = time.monotonic() - t0
                print(
                    f"[{i}] {len(data)} bytes "
                    f"in {elapsed:.3f}s: "
                    f"{data[:64].hex(' ')}"
                )

            except usb.core.USBError as e:
                if getattr(e, "errno", None) == 110:
                    print(f"[{i}] TIMEOUT")
                else:
                    print(f"[{i}] USB ERROR: {e}")
                    break

    except usb.core.USBError as e:
        print("Claim failed:", e)

    finally:
        if claimed:
            usb.util.release_interface(dev, iface)

usb.util.dispose_resources(dev)
