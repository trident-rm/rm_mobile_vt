from __future__ import annotations

import logging
from pathlib import Path

from vt13_video.config import AppConfig
from vt13_video.nal import PARAMETER_SET_TYPES, scan_nals
from vt13_video.pipeline import VT13Stream
from vt13_video.sources import FileSource


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CAPTURE = ROOT / "captures" / "cold_start" / "bulk_if0_ep81.bin"
GOLDEN_TIMES = ROOT / "captures" / "cold_start" / "bulk_if0_ep81.times.tsv"
NEGATIVE_CAPTURE = ROOT / "captures" / "vt13_live_raw.h265"

_LOGGER = logging.getLogger("vt13_video.tests")
_LOGGER.addHandler(logging.NullHandler())
_LOGGER.propagate = False
_LOGGER.setLevel(logging.CRITICAL)


def make_nal(
    nal_type: int,
    payload: bytes = b"",
    *,
    start_code: bytes = b"\x00\x00\x01",
    first_slice: bool = False,
    temporal_id: int = 1,
) -> bytes:
    """Build a syntactically valid NAL unit for parser/assembler tests."""
    if not 0 <= nal_type <= 63:
        raise ValueError("nal_type must fit in six bits")
    if temporal_id < 1:
        raise ValueError("temporal_id_plus1 must be nonzero")
    header = bytes([(nal_type << 1) & 0x7E, temporal_id & 0x07])
    body = payload
    if first_slice:
        if body:
            body = bytes([body[0] | 0x80]) + body[1:]
        else:
            body = b"\x80"
    return start_code + header + body


def make_non_irap_chunk() -> bytes:
    """Two AUD-delimited TRAIL_R pictures, neither of which is an IRAP."""
    audit = make_nal(35, b"\x30")
    trail = make_nal(1, b"\x00", first_slice=True)
    return audit + trail + audit + trail


def strip_parameter_sets(source_path: Path, output_path: Path) -> Path:
    nals = scan_nals(source_path.read_bytes())
    output_path.write_bytes(
        b"".join(nal.raw for nal in nals if nal.nal_type not in PARAMETER_SET_TYPES)
    )
    return output_path


def run_stream(
    path: Path,
    *,
    parameter_sets_file: Path | None = None,
    timeout: float = 60.0,
) -> tuple[VT13Stream, list]:
    """Run a capture to EOF and return the pipeline plus all queued frames."""
    config = AppConfig()
    config.output.preview = False
    config.decoder.queue_size = 256
    config.decoder.drop_oldest = False
    config.decoder.parameter_sets_file = parameter_sets_file

    source = FileSource(path, read_size=config.read.read_size, logger=_LOGGER)
    stream = VT13Stream(config, source=source, logger=_LOGGER)
    stream.start()
    stream.join(timeout)
    if stream.is_running:
        stream.stop()
        stream.join(5.0)
        raise AssertionError("pipeline did not finish before the test timeout")

    frames = []
    while True:
        frame = stream.read_frame(0)
        if frame is None:
            break
        frames.append(frame)
    return stream, frames
