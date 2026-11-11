#!/usr/bin/env python3
"""D3b offline AU replay: split an Annex-B HEVC file into access units and
send them to the C worker over a Unix SOCK_SEQPACKET socket.

The sender is the server: it binds the socket, waits for the worker to
connect, then streams AUs at the requested rate. If the worker cannot keep
up, non-IRAP AUs are dropped until the next IRAP (whole-GOP drop), and the
number is reported.
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
import time

MAGIC = 0x44574155
FLAG_IRAP = 1
FLAG_EOS = 2
IRAP_TYPES = set(range(16, 22))
HDR = struct.Struct("<IIIIQ")


def split_aus(data: bytes) -> list[tuple[int, int, bool]]:
    """Split Annex-B into AUs, attaching prefix NALs to the following AU.

    Mirrors the live pipeline's AccessUnitAssembler: VPS/SPS/PPS/AUD/prefix SEI
    belong to the *next* picture, suffix SEI/filler to the current one.  An
    earlier version started each AU at the first VCL NAL, which left the IRAP
    without its parameter sets and made a replay fail with POLLERR.
    """
    n = len(data)
    starts: list[int] = []
    pos = 0
    while True:
        i = data.find(b"\x00\x00\x01", pos)
        if i < 0:
            break
        starts.append(i)
        pos = i + 3

    nals: list[tuple[int, int, int, bool]] = []
    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else n
        hdr = s + (3 if data[s + 2] == 1 else 4)
        if hdr + 1 >= n:
            continue
        nal_type = (data[hdr] >> 1) & 0x3F
        first_slice = bool(nal_type <= 31 and hdr + 2 < n and (data[hdr + 2] & 0x80))
        nals.append((s, end, nal_type, first_slice))

    if not nals:
        return []

    aus: list[tuple[int, int, bool]] = []
    au_start = nals[0][0]
    have_vcl = False
    au_irap = False
    pending_start: int | None = None
    for s, end, nal_type, first_slice in nals:
        is_vcl = nal_type <= 31
        if is_vcl and first_slice:
            if have_vcl:
                cut = pending_start if pending_start is not None else s
                if cut > au_start:
                    aus.append((au_start, cut - au_start, au_irap))
                au_start = cut
                au_irap = False
            have_vcl = True
            pending_start = None
            if nal_type in IRAP_TYPES:
                au_irap = True
            continue
        if is_vcl:
            if not have_vcl:
                pending_start = None
            continue
        if have_vcl and nal_type in (38, 40):
            continue  # suffix SEI / filler belongs to the current picture
        if have_vcl and pending_start is None:
            pending_start = s  # prefix NALs open the next picture
    if have_vcl:
        aus.append((au_start, n - au_start, au_irap))
    return aus


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--socket", required=True)
    ap.add_argument("--rate", type=float, default=60.0, help="AU/s")
    ap.add_argument("--frames", type=int, default=0, help="0 = all AUs")
    ap.add_argument("--stall-ms", type=int, default=200, help="max block before dropping")
    ap.add_argument("--eos-wait", type=float, default=10.0)
    args = ap.parse_args()

    data = open(args.file, "rb").read()
    aus = split_aus(data)
    if args.frames > 0:
        aus = aus[: args.frames]
    print(f"file={args.file} bytes={len(data)} aus={len(aus)} rate={args.rate}", flush=True)

    path = args.socket
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    srv.bind(path)
    srv.listen(1)
    print(f"LISTENING {path}", flush=True)
    conn, _ = srv.accept()
    conn.setblocking(False)
    print("worker connected", flush=True)

    sent = 0
    dropped = 0
    recoveries = 0
    dropping = False
    bytes_sent = 0
    t0 = time.monotonic()
    period = 1.0 / args.rate if args.rate > 0 else 0.0
    next_at = t0

    for idx, (off, length, irap) in enumerate(aus):
        # Mirror the live client: a worker rebuild ("R") means the current GOP
        # can no longer be decoded, so drop non-IRAP AUs until the next IRAP
        # instead of queueing stale pictures.
        try:
            while True:
                ev = conn.recv(16, socket.MSG_DONTWAIT)
                if not ev:
                    break
                if ev == b"R":
                    recoveries += 1
                    dropping = True
        except BlockingIOError:
            pass
        except OSError:
            break
        if period:
            next_at += period
            delay = next_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        if dropping and not irap:
            dropped += 1
            continue
        if dropping and irap:
            dropping = False
        msg = HDR.pack(MAGIC, length, idx, FLAG_IRAP if irap else 0, time.monotonic_ns()) + data[off:off + length]
        deadline = time.monotonic() + args.stall_ms / 1000.0
        while True:
            try:
                conn.send(msg)
                sent += 1
                bytes_sent += length
                break
            except BlockingIOError:
                remain = deadline - time.monotonic()
                if remain <= 0:
                    dropped += 1
                    dropping = True
                    break
                time.sleep(min(remain, 0.002))
            except BrokenPipeError:
                print("worker closed the socket", flush=True)
                return 1
        if sent % 60 == 0:
            dt = time.monotonic() - t0
            print(f"sent={sent} dropped={dropped} {sent / dt:.1f} AU/s", flush=True)

    eos = HDR.pack(MAGIC, 0, len(aus), FLAG_EOS, time.monotonic_ns())
    deadline = time.monotonic() + args.eos_wait
    while time.monotonic() < deadline:
        try:
            conn.send(eos)
            print("EOS sent", flush=True)
            break
        except BlockingIOError:
            time.sleep(0.01)
        except BrokenPipeError:
            print("worker closed before EOS", flush=True)
            return 1
    conn.close()
    srv.close()
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    dt = time.monotonic() - t0
    print(f"SENT={sent} DROPPED={dropped} RECOVERIES={recoveries} BYTES={bytes_sent} "
          f"WALL={dt:.3f}s FPS={sent / dt if dt else 0:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
