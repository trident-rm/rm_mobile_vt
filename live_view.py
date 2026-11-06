#!/usr/bin/env python3
"""VT13 EP0x81 HEVC -> PyAV -> OpenCV experimental viewer.

Modes:
  Offline: python vt13_live_view.py --file captures/cold_start/bulk_if0_ep81.bin --headless --save-first /tmp/vt13_pyav.png
  Live:    sudo -E "$(which python3)" vt13_live_view.py --live --seconds 40 --headless --save-first /tmp/vt13_live.png

Install: python -m pip install av opencv-python pyusb

Notes:
  - It does not send any undocumented DJI OUT requests, issue device resets,
    or synthesize missing parameter sets.
  - Decoding may not start until a real VPS/SPS/PPS/IRAP arrives.
  - Reopening USB after EIO does not guarantee a gap-free HEVC stream.
"""
import argparse
import time
from pathlib import Path

VID, PID = 0x2CA3, 0x1020
IFACE, EP = 0, 0x81

class Viewer:
    def __init__(self, headless, save_first, preview_width):
        import av
        self.av = av
        self.decoder = av.CodecContext.create('hevc', 'r')
        self.headless = headless
        self.save_first = save_first
        self.preview_width = preview_width
        self.frames = 0
        self.errors = 0
        self._saved = False
        if not headless or save_first:
            import cv2
            self.cv2 = cv2
        else:
            self.cv2 = None

    def feed(self, data):
        try:
            packets = self.decoder.parse(data)
        except self.av.error.FFmpegError as ex:
            self.errors += 1
            if self.errors <= 5:
                print('HEVC parse error:', ex, flush=True)
            return True
        for packet in packets:
            try:
                frames = self.decoder.decode(packet)
            except self.av.error.FFmpegError as ex:
                self.errors += 1
                if self.errors <= 5:
                    print('HEVC decode error:', ex, flush=True)
                continue
            for frame in frames:
                self.frames += 1
                if self.cv2 is None:
                    if self.frames == 1 or self.frames % 60 == 0:
                        print('Decoded frame', self.frames, frame.width, 'x', frame.height, flush=True)
                    continue
                bgr = frame.to_ndarray(format='bgr24')
                if self.save_first and not self._saved:
                    self.save_first.parent.mkdir(parents=True, exist_ok=True)
                    self.cv2.imwrite(str(self.save_first), bgr)
                    print(f'Saved first decoded frame: {self.save_first} ({frame.width}x{frame.height})', flush=True)
                    self._saved = True
                if not self.headless:
                    if self.preview_width and frame.width > self.preview_width:
                        w = self.preview_width
                        h = max(2, round(frame.height * w / frame.width))
                        preview = self.cv2.resize(bgr, (w, h))
                    else:
                        preview = bgr
                    self.cv2.imshow('VT13 USB HEVC (press q to quit)', preview)
                    if self.cv2.waitKey(1) & 0xFF == ord('q'):
                        return False
        return True

    def finish(self):
        try:
            self.feed(b'')
        except Exception:
            pass
        if self.cv2 is not None and not self.headless:
            self.cv2.destroyAllWindows()
        print(f'Decoded frames: {self.frames}; decoder parse/decode errors: {self.errors}')


def open_usb():
    import usb.core
    import usb.util
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        raise RuntimeError('VT13 2ca3:1020 not found')
    cfg = dev.get_active_configuration()
    if EP not in [int(e.bEndpointAddress) for e in cfg[(IFACE, 0)]]:
        raise RuntimeError('EP 0x81 is unavailable')
    if dev.is_kernel_driver_active(IFACE):
        raise RuntimeError('Kernel driver owns USB interface 0; not detaching automatically')
    usb.util.claim_interface(dev, IFACE)
    return dev


def close_usb(dev):
    if dev is None:
        return
    import usb.util
    try:
        usb.util.release_interface(dev, IFACE)
    except Exception:
        pass
    try:
        usb.util.dispose_resources(dev)
    except Exception:
        pass


def run_live(args, viewer):
    import usb.core
    start = time.monotonic()
    total = 0
    dev = None
    errors = 0
    recorded = None
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        recorded = args.record.open('wb')
    try:
        while time.monotonic() - start < args.seconds:
            if dev is None:
                try:
                    dev = open_usb()
                    print(f'[{time.monotonic()-start:.2f}s] EP0x81 opened', flush=True)
                except Exception as ex:
                    print(f'[{time.monotonic()-start:.2f}s] USB open failed: {ex}', flush=True)
                    time.sleep(args.retry_delay)
                    continue
            try:
                buf = bytes(dev.read(EP, args.read_size, timeout=args.timeout_ms))
            except usb.core.USBError as ex:
                if getattr(ex, 'errno', None) == 110 or getattr(ex, 'backend_error_code', None) == -7:
                    continue
                errors += 1
                print(f'[{time.monotonic()-start:.2f}s] EP81 read error errno={getattr(ex,"errno",None)} backend={getattr(ex,"backend_error_code",None)}', flush=True)
                close_usb(dev)
                dev = None
                time.sleep(args.retry_delay)
                continue
            if not buf:
                continue
            total += len(buf)
            if recorded is not None:
                recorded.write(buf)
            if not viewer.feed(buf):
                break
    except KeyboardInterrupt:
        print('Interrupted.')
    finally:
        close_usb(dev)
        if recorded is not None:
            recorded.close()
        print(f'USB bytes={total:,}; USB errors={errors}; elapsed={time.monotonic()-start:.2f}s')


def run_file(args, viewer):
    with args.file.open('rb') as fh:
        while True:
            buf = fh.read(args.read_size)
            if not buf:
                break
            if not viewer.feed(buf):
                break


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--live', action='store_true')
    g.add_argument('--file', type=Path)
    ap.add_argument('--seconds', type=float, default=40.0)
    ap.add_argument('--headless', action='store_true')
    ap.add_argument('--save-first', type=Path, default=None)
    ap.add_argument('--preview-width', type=int, default=1000)
    ap.add_argument('--read-size', type=int, default=16384)
    ap.add_argument('--timeout-ms', type=int, default=250)
    ap.add_argument('--retry-delay', type=float, default=0.5)
    ap.add_argument('--record', type=Path, help='Live mode: save exact raw EP81 bytes')
    args = ap.parse_args()
    viewer = Viewer(args.headless, args.save_first, args.preview_width)
    try:
        if args.live:
            run_live(args, viewer)
        else:
            run_file(args, viewer)
    finally:
        viewer.finish()

if __name__ == '__main__':
    main()