#!/usr/bin/env python3
"""Audit RoboMaster VT13 USB EP 0x81 for HEVC Annex-B NAL units.

Read-only/offline tool: does not communicate with the USB device.
Example:
  python vt13_hevc_audit.py captures/linked/bulk_if0_ep81.bin
  python vt13_hevc_audit.py captures/relink/bulk_if0_ep81.bin --params-out vt13_params.h265
"""
import argparse
from collections import Counter
from pathlib import Path
import re
from statistics import median

NAL_NAMES = {
    0: 'TRAIL_N', 1: 'TRAIL_R', 19: 'IDR_W_RADL', 20: 'IDR_N_LP',
    21: 'CRA', 32: 'VPS', 33: 'SPS', 34: 'PPS', 35: 'AUD',
    39: 'PREFIX_SEI', 40: 'SUFFIX_SEI'
}
STARTS = re.compile(rb'\x00\x00\x00\x01|\x00\x00\x01')

def scan(data):
    boundaries = list(STARTS.finditer(data))
    out = []
    for i, m in enumerate(boundaries):
        s = m.end()
        e = boundaries[i + 1].start() if i + 1 < len(boundaries) else len(data)
        if s + 2 > e:
            continue
        a, b = data[s:s + 2]
        nal_type = (a >> 1) & 63
        layer = ((a & 1) << 5) | (b >> 3)
        tid = b & 7
        valid_header = not (a & 0x80) and tid != 0
        out.append({
            'start': m.start(), 'end': e, 'header': f'{a:02x} {b:02x}',
            'type': nal_type, 'layer': layer, 'tid': tid,
            'length': e - m.start(), 'valid_header': valid_header,
            'raw': data[m.start():e]
        })
    return out

def report(path, params_out=None):
    data = path.read_bytes()
    nal = scan(data)
    valid = [n for n in nal if n['valid_header']]
    types = Counter(n['type'] for n in valid)
    print(f'\n=== {path} ===')
    print(f'Bytes: {len(data):,}, start-code candidates: {len(nal):,}, valid HEVC headers: {len(valid):,}')
    for typ, count in types.most_common():
        lengths = [n['length'] for n in valid if n['type'] == typ]
        print(f'  type {typ:2d} {NAL_NAMES.get(typ, "OTHER"):12s}  count={count:5d}  median_bytes={median(lengths):,.0f}')
    print('First 18 NAL units:')
    for n in valid[:18]:
        print(f"  at {n['start']:>9,}  type={n['type']:2d} {NAL_NAMES.get(n['type'], 'OTHER'):12s} len={n['length']:>7,}  hdr={n['header']}  layer={n['layer']} tid={n['tid']}")
    # Group all NALs from one AUD (35) to the next AUD.
    groups = []
    current = None
    for n in valid:
        if n['type'] == 35:
            if current is not None:
                groups.append(current)
            current = [n]
        elif current is not None:
            current.append(n)
    if current is not None:
        groups.append(current)
    print(f'AUD-delimited groups: {len(groups):,}')
    if groups:
        patterns = Counter(tuple(n['type'] for n in group) for group in groups)
        print('Most common AUD group NAL sequences:')
        for pattern, c in patterns.most_common(8):
            print(f'  {c:5d} x {pattern}')
        sizes = [sum(n['length'] for n in group) for group in groups]
        print(f'Median AUD group wire size: {median(sizes):,.0f} B')
    # Parameter sets and random-access NALs needed to start decoding.
    param_types = [32, 33, 34]
    missing = [NAL_NAMES[t] for t in param_types if types[t] == 0]
    irap = sum(types[t] for t in range(16, 24))
    print('Missing HEVC parameter sets:', ', '.join(missing) if missing else 'none')
    print('IRAP / random-access picture NAL count (types 16..23):', irap)
    if params_out:
        selected = []
        for t in param_types:
            selected.extend(n['raw'] for n in valid if n['type'] == t)
        outpath = Path(params_out)
        if selected:
            outpath.write_bytes(b''.join(selected))
            print(f'Saved {len(selected)} parameter-set NALs to {outpath}')
        else:
            print('No parameter sets found; no params file created.')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--params-out', default=None)
    args = p.parse_args()
    report(args.file, args.params_out)

if __name__ == '__main__':
    main()