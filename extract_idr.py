#!/usr/bin/env python3
"""Extract HEVC segments beginning with an observed VPS/SPS/PPS+IRAP sequence.

Uses exact bytes captured from VT13 endpoint 0x81; does not invent codec data.
A resulting file is a candidate self-contained HEVC segment, not a guarantee of
complete decoding if USB read gaps have dropped data.

Usage:
    python vt13_extract_idr.py captures/cold_start/bulk_if0_ep81.bin \
        --out captures/cold_start/idr_segments
"""
import argparse
import re
from pathlib import Path

PATTERN = re.compile(rb'\x00\x00\x00\x01|\x00\x00\x01')

def parse_nals(data):
    markers = list(PATTERN.finditer(data))
    nals = []
    for i, marker in enumerate(markers):
        p = marker.start()
        hdr = marker.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(data)
        if hdr + 2 > end:
            continue
        a, b = data[hdr:hdr+2]
        if a & 0x80 or (b & 7) == 0:
            continue
        typ = (a >> 1) & 63
        nals.append((p, end, typ))
    return nals

def read_gap_boundaries(raw_file, expected_len, min_gap):
    """Return byte offsets where the USB read timestamps show a real-time gap."""
    stamps = raw_file.with_suffix('.times.tsv')
    if not stamps.is_file():
        return []
    offsets = []
    prev_t = None
    total = 0
    try:
        for i, line in enumerate(stamps.read_text().splitlines()):
            if i == 0 or not line.strip():
                continue
            t, n = line.split('\t')[:2]
            t, n = float(t), int(n)
            if prev_t is not None and t - prev_t > min_gap:
                offsets.append(total)
            total += n
            prev_t = t
    except (ValueError, IndexError) as ex:
        print('Warning: timestamps cannot be parsed:', ex)
        return []
    if total != expected_len:
        print('Warning: timestamps do not cover raw file; ignoring gap boundaries')
        return []
    return offsets

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('file', type=Path)
    ap.add_argument('--out', type=Path, default=Path('idr_segments'))
    ap.add_argument('--min-size', type=int, default=1024, help='Minimum output bytes')
    ap.add_argument('--max-gap', type=float, default=0.5,
                    help='Cut a candidate stream at USB read gap > this many seconds')
    args = ap.parse_args()
    raw = args.file.read_bytes()
    nals = parse_nals(raw)
    gaps = read_gap_boundaries(args.file, len(raw), args.max_gap)
    print(f'USB read gap boundaries: {len(gaps)}')
    args.out.mkdir(parents=True, exist_ok=True)
    print('NALs:', len(nals), 'IRAP NALs:', sum(16 <= n[2] <= 23 for n in nals))
    count = 0
    for k, (start, end, typ) in enumerate(nals):
        if not 16 <= typ <= 23:
            continue
        # Require the observed contiguous HEVC parameter-set sequence just before IRAP.
        if k < 3 or [n[2] for n in nals[k-3:k]] != [32, 33, 34]:
            print(f'IRAP at {start:,}: no immediately preceding VPS/SPS/PPS, skipped')
            continue
        p = nals[k-3][0]  # start at VPS; no preceding TRAIL_R from a different AU
        # Stop before next VPS sequence; data after stream gaps can be corrupt.
        next_vps = next((n[0] for n in nals[k+1:] if n[2] == 32), len(raw))
        next_gap = next((g for g in gaps if g > p), len(raw))
        stop = min(next_vps, next_gap)
        if stop < end or stop - p < args.min_size:
            print(f'IRAP at {start:,}: no complete slice before next gap, skipped')
            continue
        count += 1
        output = args.out / f'vt13_idr_{count:02d}.h265'
        output.write_bytes(raw[p:stop])
        print(f'{output}: {stop-p:,} bytes; VPS at {p:,}, IRAP type {typ} at {start:,}')
    if not count:
        print('No contiguous VPS/SPS/PPS/IRAP runs found.')

if __name__ == '__main__':
    main()