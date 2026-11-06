#!/usr/bin/env python3
"""VT13 DJI C5 USB video-path investigation.

Purpose: simultaneously record all plausible USB input data paths, characterize
unknown framing, and extract candidate elementary streams for FFmpeg testing.
NOT a verified VT13 video decoder: video startup protocol remains unknown.

Dependencies for capture: python -m pip install pyusb pyserial
Usage:
  sudo "$(which python)" vt13_usb_video_lab.py capture --out captures/idle --seconds 5
  python vt13_usb_video_lab.py analyze captures/idle
  python vt13_usb_video_lab.py analyze /path/to/vt13_idle.bin
  python vt13_usb_video_lab.py extract captures/idle/bulk_if1_ep82.bin \
      --mode framed --out /tmp/ep82_candidate.h265
  python vt13_usb_video_lab.py compare captures/idle captures/linked

Safety: no USB vendor writes, firmware commands, reset, or driver detachment.
CDC serial ports opened with DTR/RTS requested off, though some drivers briefly
assert signals on open. No start-video handshake is attempted.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import threading
import time

VID, PID = 0x2CA3, 0x1020
HEAD_TYPES = (0xF5, 0xF6, 0xF7, 0xF8)
# Confirmed from user supplied descriptors. CDC data interface 3 and 5 -> Linux ttyACM0/1.
BULKS = [(0, 0x81), (1, 0x82)]


def bit_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    freq = collections.Counter(data)
    return -sum((n / len(data)) * math.log2(n / len(data)) for n in freq.values())


def start_codes(data: bytes):
    """Find Annex-B NAL start code candidates, no assumption about codec.
    Yields (position, 3 or 4, byte0, byte1).
    """
    pos = 0
    while pos < len(data) - 5:
        a = data.find(b'\x00\x00\x01', pos)
        if a < 0:
            return
        # Extended 4-byte code might start one byte earlier.
        start = a - 1 if a > 0 and data[a - 1] == 0 else a
        size = 4 if start != a else 3
        j = start + size
        if j + 1 < len(data):
            yield start, size, data[j], data[j + 1]
        pos = a + 3


def nal_scan(data: bytes) -> dict:
    out = collections.Counter()
    for pos, size, x, y in start_codes(data):
        out['annexb_candidates'] += 1
        if (x & 0x80) == 0 and (x & 0x1f) not in (0, 30, 31):
            t = x & 0x1f
            out['h264_plausible'] += 1
            if t in (5, 7, 8):
                out['h264_type_%d' % t] += 1
        h = (x >> 1) & 0x3f
        if (x & 0x80) == 0 and 0 < (y & 7) <= 7 and h <= 40:
            out['h265_plausible'] += 1
            if h in (19, 20, 21, 32, 33, 34):
                out['h265_type_%d' % h] += 1
    out['jpeg_soi_candidates'] = data.count(b'\xff\xd8\xff')
    out['mp4_ftyp_candidates'] = data.count(b'ftyp')
    out['mpeg_ts_188_sync_candidates'] = sum(
        1 for off in range(min(188, len(data)))
        if len(data) > off + 188 * 4
        and all(data[off + n * 188] == 0x47 for n in range(5))
    )
    return dict(out)


def frames(raw: bytes):
    """Parse user-observed 0xF5..0xF8,0x64 + LE16 inclusive length.
    Verified on idle sample, NOT documented DJI header standard.
    Only accept frame boundaries that align with next plausible header or EOF.
    """
    p, skips = 0, 0
    N = len(raw)
    while p + 4 <= N:
        if raw[p] not in HEAD_TYPES or raw[p+1] != 0x64:
            p += 1
            skips += 1
            continue
        length = int.from_bytes(raw[p+2:p+4], 'little')
        if length < 20 or length > 65535 or p + length > N:
            p += 1
            skips += 1
            continue
        end = p + length
        if end < N and not (end + 4 <= N and raw[end] in HEAD_TYPES and raw[end+1] == 0x64 and
                            20 <= int.from_bytes(raw[end+2:end+4], 'little') <= 65535):
            p += 1
            skips += 1
            continue
        f = raw[p:end]
        ident = int.from_bytes(f[16:18], 'little')
        nested = int.from_bytes(f[18:20], 'little')
        hdr = 20 if f[0] == 0xF5 else 24
        layout_ok = (f[0] != 0xF7 and len(f) - nested == hdr)
        yield (p, f[0], ident, length, hdr, layout_ok, f)
        p = end
    # Note: if needed detect uncaptured truncated last frame separately.


def byte_report(path: Path, max_mb=256):
    if path.stat().st_size > max_mb * 1024 * 1024:
        return {'file':str(path),'error':f'File exceeds analysis limit {max_mb} MiB'}
    raw = path.read_bytes()
    typ = collections.Counter()
    mid = collections.Counter()
    length_hist = collections.Counter()
    layouts = collections.Counter()
    parsed_bytes = 0
    payload_candidates = bytearray()
    for off, t, ident, n, hdr, ok, f in frames(raw):
        typ[f'{t:02X}'] += 1
        mid[f'{t:02X}:{ident:04X}'] += n
        length_hist[n] += 1
        layouts['compatible' if ok else 'unknown'] += 1
        parsed_bytes += n
        if ok:
            payload_candidates.extend(f[hdr:])
    return {
        'file':str(path),'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(),
        'entropy_bits_per_byte':round(bit_entropy(raw),3),
        'zero_fraction':round(raw.count(b'\x00')/max(1,len(raw)), 4),
        'frames':sum(typ.values()), 'framed_bytes':parsed_bytes, 'unframed_bytes':len(raw)-parsed_bytes,
        'framed_types':dict(typ),'layout_counts':dict(layouts),
        'largest_frame_bytes':max(length_hist,default=0),
        'top_ids_by_wire_bytes':mid.most_common(15),
        'top_frame_lengths':length_hist.most_common(12),
        'video_signatures_raw':nal_scan(raw),
        'video_signatures_known_payloads':nal_scan(bytes(payload_candidates)),
    }


def safe_write_json(p:Path, info):
    p.write_text(json.dumps(info,ensure_ascii=False,indent=2) + '\n', encoding='utf-8')


def find_ports():
    """Only map CDC ports that advertise the exact DJI VID:PID.
    Do not assume ttyACM numbering is stable.
    """
    try:
        from serial.tools import list_ports
    except ImportError:
        return [], 'pyserial missing; python -m pip install pyserial'
    ps=[]
    for p in list_ports.comports():
        if p.vid == VID and p.pid == PID:
            ps.append({'port':p.device,'description':p.description, 'location':p.location,'interface':p.interface})
    return ps, None


def capture(args):
    try:
        import usb.core
        import usb.util
    except ImportError:
        raise SystemExit('Need PyUSB: python -m pip install pyusb (not pip install usb)')
    dev = usb.core.find(idVendor=VID,idProduct=PID)
    if dev is None:
        raise SystemExit('2ca3:1020 not found. Check lsusb, USB connection and permissions.')
    cfg = dev.get_active_configuration()
    path = Path(args.out)
    path.mkdir(parents=True, exist_ok=True)
    ports, perr = find_ports()
    info = {
        'device': '2ca3:1020','configuration':cfg.bConfigurationValue,
        'interfaces': [],'detected_cdc':ports,'cdc_error':perr,
        'start_wallclock':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'requested_seconds':args.seconds,'description':'read-only endpoint data probe; not a decoded video stream',
        'warnings': ['CDC port open may toggle DTR/RTS despite attempting to set low',
                     'Only USB standard descriptors are read via control endpoint EP0',
                     'No vendor USB OUT commands, no reset, no driver detach']
    }
    for it in cfg:
        info['interfaces'].append({
            'interface':int(it.bInterfaceNumber),'name':(usb.util.get_string(dev, it.iInterface) if it.iInterface else ''),
            'class':int(it.bInterfaceClass),'subclass':int(it.bInterfaceSubClass),
            'protocol':int(it.bInterfaceProtocol),
            'endpoints':[f'0x{int(ep.bEndpointAddress):02x}' for ep in it]
        })
    try:
        info['device_manufacturer']=usb.util.get_string(dev,dev.iManufacturer)
        info['device_product']=usb.util.get_string(dev,dev.iProduct)
    except Exception:
        pass
    safe_write_json(path/'device.json',info)
    print('Device detected; writing to:',path)
    print('Available CDC ports:',ports)
    # Each worker owns its own libusb device handle; shared device, separate interfaces.
    start_evt=threading.Event()
    stop_evt=threading.Event()
    results={}
    mu=threading.Lock()

    def bulk_reader(iface,ep):
        name=f'bulk_if{iface}_ep{ep:02x}'
        stats={'interface':iface,'endpoint':f'0x{ep:02x}','bytes':0,'reads':0,'timeouts':0}
        handle=None
        claimed=False
        try:
            handle=usb.core.find(idVendor=VID,idProduct=PID)
            if handle is None:
                raise RuntimeError('device disappeared')
            actual_eps = [int(x.bEndpointAddress) for x in handle.get_active_configuration()[(iface,0)]]
            if ep not in actual_eps:
                raise RuntimeError(f'EP {ep:02x} not in interface {iface}')
            if handle.is_kernel_driver_active(iface):
                raise RuntimeError(f'kernel driver active on iface {iface}, not detaching')
            usb.util.claim_interface(handle,iface)
            claimed=True
            start_evt.wait()
            with (path/f'{name}.bin').open('wb') as output, (path/f'{name}.times.tsv').open('w') as stamps:
                stamps.write('elapsed_s\tchunk_length\n')
                while not stop_evt.is_set() and stats['bytes'] < args.max_mb * 1024 * 1024:
                    try:
                        chunk=bytes(handle.read(ep,args.read_size,timeout=args.timeout_ms))
                    except usb.core.USBError as e:
                        if getattr(e,'errno',None)==110 or 'timed out' in str(e).lower():
                            stats['timeouts']+=1
                            continue
                        raise
                    if chunk:
                        chunk=chunk[:args.max_mb*1024*1024-stats['bytes']]
                        output.write(chunk)
                        stamps.write(f'{time.monotonic()-start_time:.6f}\t{len(chunk)}\n')
                        stats['bytes']+=len(chunk)
                        stats['reads']+=1
        except Exception as e:
            stats['error']=repr(e)
        finally:
            if handle is not None:
                if claimed:
                    try: usb.util.release_interface(handle,iface)
                    except Exception: pass
                usb.util.dispose_resources(handle)
            with mu: results[name]=stats

    def serial_reader(port):
        name='serial_'+Path(port).name
        stats={'port':port,'bytes':0,'reads':0,'timeouts':0}
        try:
            import serial
            ser=serial.Serial(port=None,baudrate=args.baud,timeout=args.timeout_ms/1000)
            ser.dtr=False
            ser.rts=False
            ser.port=port
            ser.open()
            start_evt.wait()
            with (path/f'{name}.bin').open('wb') as output, (path/f'{name}.times.tsv').open('w') as stamps:
                stamps.write('elapsed_s\tchunk_length\n')
                while not stop_evt.is_set() and stats['bytes'] < args.max_mb*1024*1024:
                    chunk=ser.read(args.read_size)
                    if chunk:
                        chunk=chunk[:args.max_mb*1024*1024-stats['bytes']]
                        output.write(chunk)
                        stamps.write(f'{time.monotonic()-start_time:.6f}\t{len(chunk)}\n')
                        stats['bytes']+=len(chunk)
                        stats['reads']+=1
                    else:
                        stats['timeouts']+=1
            ser.close()
        except Exception as e:
            stats['error']=repr(e)
        with mu: results[name]=stats

    jobs=[]
    if not args.skip_bulk:
        for iface,ep in BULKS:
            jobs.append(threading.Thread(target=bulk_reader,args=(iface,ep),daemon=True))
    if not args.skip_serial:
        for p in ports:
            jobs.append(threading.Thread(target=serial_reader,args=(p['port'],),daemon=True))
    if not jobs:
        raise SystemExit('No endpoints enabled')
    for j in jobs: j.start()
    # Give claim_interface/open time; no sleeps once capture starts.
    time.sleep(0.4)
    start_time=time.monotonic()
    start_evt.set()
    print(f'Capturing {args.seconds:.1f}s across {len(jobs)} channel(s).')
    try:
        while time.monotonic()-start_time < args.seconds:
            time.sleep(0.05)
    except KeyboardInterrupt:
        print('Interrupted, saving partial output.')
    finally:
        stop_evt.set()
    for j in jobs: j.join(timeout=max(3,args.timeout_ms/1000+2))
    elapsed=time.monotonic()-start_time
    for v in results.values():
        v['elapsed_s']=round(elapsed,3)
        v['bytes_per_second']=round(v['bytes']/max(elapsed,.001),1)
    safe_write_json(path/'capture.json',results)
    print(json.dumps(results,ensure_ascii=False,indent=2))
    print('EP0 standard descriptors recorded in device.json, no unknown control requests issued.')


def input_bins(target):
    p=Path(target)
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(p.glob('*.bin'))
    raise SystemExit(f'No such file or directory: {p}')


def analyze(args):
    all_stats=[]
    for f in input_bins(args.target):
        stats=byte_report(f,args.max_mb)
        all_stats.append(stats)
        print(f'\n===== {f} =====')
        print(json.dumps(stats,indent=2,ensure_ascii=False))
    if args.report:
        safe_write_json(Path(args.report),all_stats)


def compare(args):
    a={p.name:byte_report(p,args.max_mb) for p in input_bins(args.baseline)}
    b={p.name:byte_report(p,args.max_mb) for p in input_bins(args.active)}
    print('Comparison (prefer equal capture duration; bytes are raw counts, not necessarily video):')
    for k in sorted(set(a)|set(b)):
        x=a.get(k,{});y=b.get(k,{})
        print(f'{k:29} idle={x.get("bytes",0):>10,}B active={y.get("bytes",0):>10,}B '
              f'delta={y.get("bytes",0)-x.get("bytes",0):>+11,}B '
              f'frames {x.get("frames",0)} -> {y.get("frames",0)}')
        print('  idle signatures:',x.get('video_signatures_raw',{}))
        print('  live signatures:',y.get('video_signatures_raw',{}))


def extract(args):
    p=Path(args.input)
    raw=p.read_bytes()
    if args.mode == 'raw':
        candidate=raw
        count=0
    else:
        selected=bytearray()
        count=0
        for pos,typ,ident,ln,hdr,ok,frame in frames(raw):
            if not ok:
                continue  # never infer payload offsets for unvalidated layouts
            if args.frame_type is not None and typ != args.frame_type:
                continue
            if args.msg_id is not None and ident != args.msg_id:
                continue
            selected.extend(frame[hdr:])
            count+=1
        candidate=bytes(selected)
    if args.trim_annexb:
        candidates=list(start_codes(candidate))
        if not candidates:
            print('WARNING: no Annex-B start code found; no trimming performed')
        else:
            candidate=candidate[candidates[0][0]:]
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(candidate)
    print(f'Extracted {len(candidate):,} bytes to {out}, source messages={count}')
    print('NAL signature probes:',nal_scan(candidate))
    print('No codec asserted. Candidate stream may be non-video, proprietary, compressed or encrypted.')
    if args.ffprobe:
        if shutil.which('ffprobe') is None:
            print('ffprobe not found (apt install ffmpeg)')
        else:
            codec='hevc' if args.codec=='h265' else 'h264'
            try:
                proc=subprocess.run(['ffprobe','-v','warning','-f',codec,'-show_entries',
                                    'stream=codec_name,width,height','-of','default=nw=1',str(out)],
                                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                     text=True,timeout=12,check=False)
                print('ffprobe exit:',proc.returncode,'output:',proc.stdout[:1500],proc.stderr[:1000])
            except subprocess.TimeoutExpired:
                print('ffprobe timed out')


def main():
    parser=argparse.ArgumentParser(description='VT13 all USB input ports: capture / diagnose / extract video candidates')
    sub=parser.add_subparsers(dest='command',required=True)
    c=sub.add_parser('capture',help='Concurrent read: 0x81 + 0x82 + ttyACM ports')
    c.add_argument('--out',default='vt13_capture')
    c.add_argument('--seconds',type=float,default=5)
    c.add_argument('--max-mb',type=int,default=64,help='Per-channel cap')
    c.add_argument('--read-size',type=int,default=16384)
    c.add_argument('--timeout-ms',type=int,default=200)
    c.add_argument('--baud',type=int,default=115200,help='CDC ACM nominal rate; not proven protocol setting')
    c.add_argument('--skip-serial',action='store_true')
    c.add_argument('--skip-bulk',action='store_true')
    a=sub.add_parser('analyze',help='Analyze one binary or all *.bin in directory')
    a.add_argument('target');a.add_argument('--report')
    a.add_argument('--max-mb',type=int,default=256)
    comp=sub.add_parser('compare',help='Compare captured USB endpoint bytes and signatures')
    comp.add_argument('baseline');comp.add_argument('active')
    comp.add_argument('--max-mb',type=int,default=256)
    x=sub.add_parser('extract',help='Extract candidate byte stream; not guaranteed playable')
    x.add_argument('input');x.add_argument('--output',required=True)
    x.add_argument('--mode',choices=('raw','framed'),default='framed')
    x.add_argument('--frame-type',type=lambda t:int(t,0),default=None,help='e.g. 0xF6')
    x.add_argument('--msg-id',type=lambda t:int(t,0),default=None,help='e.g. 0x1020')
    x.add_argument('--trim-annexb',action='store_true')
    x.add_argument('--ffprobe',action='store_true')
    x.add_argument('--codec',choices=('h264','h265'),default='h265')
    args=parser.parse_args()
    {'capture':capture,'analyze':analyze,'compare':compare,'extract':extract}[args.command](args)

if __name__ == '__main__':
    main()
