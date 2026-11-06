#!/usr/bin/env python3
"""Consume decoded VT13 frames as OpenCV-compatible BGR arrays."""
from __future__ import annotations

import argparse
from pathlib import Path

from vt13_video import FileSource, VT13Stream, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read BGR frames from VT13 video")
    parser.add_argument("--config", type=Path, default=None, help="YAML configuration file")
    parser.add_argument("--file", type=Path, default=None, help="replay a raw capture instead of USB")
    parser.add_argument("--seconds", type=float, default=10.0, help="stop after N seconds (0 = forever)")
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    config = load_config(arguments.config)
    config.output.preview = False
    config.runtime.max_seconds = arguments.seconds

    source = None
    if arguments.file is not None:
        source = FileSource(
            arguments.file.expanduser().resolve(),
            read_size=config.read.read_size,
        )

    last_sequence = -1
    try:
        with VT13Stream(config, source=source) as stream:
            while stream.is_running or stream.frames.qsize() > 0:
                frame = stream.read_frame(0.5)
                if frame is None:
                    if not stream.is_running:
                        break
                    # Keep the newest frame available even when the queue is empty.
                    frame = stream.latest_frame
                if frame is None or frame.sequence == last_sequence:
                    continue
                last_sequence = frame.sequence
                image = frame.image  # numpy.ndarray, BGR uint8
                print(
                    f"frame={frame.sequence} size={frame.width}x{frame.height} "
                    f"shape={image.shape} latency={frame.latency_s:.3f}s"
                )
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
