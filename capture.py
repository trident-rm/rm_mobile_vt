
import time
import usb.core
import usb.util

VID = 0x2CA3
PID = 0x1020
IFACE = 1
ENDPOINT = 0x82

DURATION = 5
MAX_BYTES = 8 * 1024 * 1024

dev = usb.core.find(idVendor=VID, idProduct=PID)
if dev is None:
    raise RuntimeError("DJI C5 not found")

if dev.is_kernel_driver_active(IFACE):
    raise RuntimeError("Interface 1 is busy")

claimed = False
total = 0
reads = 0

try:
    usb.util.claim_interface(dev, IFACE)
    claimed = True

    start = time.monotonic()

    with open("vt13_idle.bin", "wb") as f:
        while (
            time.monotonic() - start < DURATION
            and total < MAX_BYTES
        ):
            try:
                data = bytes(dev.read(
                    ENDPOINT, 4096, timeout=200
                ))
            except usb.core.USBTimeoutError:
                continue

            if data:
                remaining = MAX_BYTES - total
                data = data[:remaining]
                f.write(data)
                total += len(data)
                reads += 1

    elapsed = time.monotonic() - start
    print(f"Reads: {reads}")
    print(f"Bytes: {total}")
    print(f"Rate: {total / elapsed / 1024:.1f} KiB/s")
    print("Saved: vt13_idle.bin")

finally:
    if claimed:
        usb.util.release_interface(dev, IFACE)
    usb.util.dispose_resources(dev)
