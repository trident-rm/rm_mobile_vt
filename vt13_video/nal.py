"""Incremental Annex-B parsing and HEVC access-unit assembly.

The VT13 endpoint emits a raw HEVC Annex-B elementary stream.  USB reads are
arbitrary chunks, so the parser must tolerate start codes and NAL units split
across reads.  Access units are assembled here before anything is handed to
the decoder; this is what lets the pipeline wait for a real random-access
picture instead of feeding incomplete or mid-picture data to FFmpeg.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


NAL_NAMES = {
    0: "TRAIL_N",
    1: "TRAIL_R",
    2: "TSA_N",
    3: "TSA_R",
    4: "STSA_N",
    5: "STSA_R",
    6: "RADL_N",
    7: "RADL_R",
    8: "RASL_N",
    9: "RASL_R",
    16: "BLA_W_LP",
    17: "BLA_W_RADL",
    18: "BLA_N_LP",
    19: "IDR_W_RADL",
    20: "IDR_N_LP",
    21: "CRA",
    22: "RSV_IRAP_22",
    23: "RSV_IRAP_23",
    32: "VPS",
    33: "SPS",
    34: "PPS",
    35: "AUD",
    39: "PREFIX_SEI",
    40: "SUFFIX_SEI",
}

PARAMETER_SET_TYPES = (32, 33, 34)
IRAP_TYPES = tuple(range(16, 24))


@dataclass(frozen=True)
class NALUnit:
    """One HEVC NAL unit, including its Annex-B start code."""

    raw: bytes
    start_code_len: int
    nal_type: int
    layer_id: int
    temporal_id: int
    payload: bytes

    @property
    def name(self) -> str:
        return NAL_NAMES.get(self.nal_type, f"TYPE_{self.nal_type}")

    @property
    def is_vcl(self) -> bool:
        return 0 <= self.nal_type <= 31

    @property
    def is_irap(self) -> bool:
        return self.nal_type in IRAP_TYPES

    @property
    def is_parameter_set(self) -> bool:
        return self.nal_type in PARAMETER_SET_TYPES

    @property
    def is_aud(self) -> bool:
        return self.nal_type == 35

    @property
    def is_sei(self) -> bool:
        return self.nal_type in (39, 40)

    @property
    def first_slice_segment_in_pic(self) -> bool:
        # For a VCL NAL, the first bit after the two-byte NAL header is
        # first_slice_segment_in_pic_flag.  Non-VCL NALs have no such flag.
        return bool(self.is_vcl and self.payload and (self.payload[0] & 0x80))

    @property
    def size(self) -> int:
        return len(self.raw)


@dataclass(frozen=True)
class AccessUnit:
    """A complete picture boundary plus any non-VCL NALs in that unit."""

    nals: tuple[NALUnit, ...]
    received_at: float

    @property
    def wire_bytes(self) -> bytes:
        return b"".join(nal.raw for nal in self.nals)

    @property
    def has_vcl(self) -> bool:
        return any(nal.is_vcl for nal in self.nals)

    @property
    def has_irap(self) -> bool:
        return any(nal.is_irap for nal in self.nals)

    @property
    def irap_types(self) -> tuple[int, ...]:
        return tuple(nal.nal_type for nal in self.nals if nal.is_irap)

    @property
    def parameter_sets(self) -> tuple[NALUnit, ...]:
        return tuple(nal for nal in self.nals if nal.is_parameter_set)

    @property
    def has_all_parameter_sets(self) -> bool:
        present = {nal.nal_type for nal in self.parameter_sets}
        return all(t in present for t in PARAMETER_SET_TYPES)

    @property
    def nal_types(self) -> tuple[int, ...]:
        return tuple(nal.nal_type for nal in self.nals)


def _find_start(buf: bytearray, start: int) -> tuple[int, int] | None:
    """Find the next Annex-B start code, normalizing 4-byte codes.

    ``bytes.find`` locates the 3-byte prefix inside a 4-byte start code.  When
    the preceding byte is also zero, report the 4-byte start code instead.
    """
    pos = buf.find(b"\x00\x00\x01", start)
    if pos < 0:
        return None
    if pos > 0 and buf[pos - 1] == 0:
        return pos - 1, 4
    return pos, 3


def parse_nal(raw: bytes, start_code_len: int) -> NALUnit | None:
    """Parse one complete NAL unit.  Return None for an invalid header."""
    if start_code_len not in (3, 4) or len(raw) < start_code_len + 2:
        return None
    a, b = raw[start_code_len], raw[start_code_len + 1]
    # forbidden_zero_bit must be zero and nuh_temporal_id_plus1 must be non-zero.
    if a & 0x80 or (b & 0x07) == 0:
        return None
    nal_type = (a >> 1) & 0x3F
    layer_id = ((a & 0x01) << 5) | (b >> 3)
    temporal_id = b & 0x07
    return NALUnit(
        raw=raw,
        start_code_len=start_code_len,
        nal_type=nal_type,
        layer_id=layer_id,
        temporal_id=temporal_id,
        payload=raw[start_code_len + 2 :],
    )


class AnnexBParser:
    """Incrementally split a byte stream into complete HEVC NAL units."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.discarded_prefix_bytes = 0
        self.invalid_nals = 0

    def feed(self, data: bytes) -> list[NALUnit]:
        if data:
            self._buf.extend(data)

        output: list[NALUnit] = []
        while True:
            first = _find_start(self._buf, 0)
            if first is None:
                # Keep enough tail to recognize a start code split across reads.
                if len(self._buf) > 3:
                    self.discarded_prefix_bytes += len(self._buf) - 3
                    del self._buf[:-3]
                break

            start, start_code_len = first
            if start > 0:
                self.discarded_prefix_bytes += start
                del self._buf[:start]

            second = _find_start(self._buf, start_code_len)
            if second is None:
                # The NAL is not complete yet; wait for the next read.
                break

            next_start, _ = second
            raw = bytes(self._buf[:next_start])
            nal = parse_nal(raw, start_code_len)
            if nal is None:
                self.invalid_nals += 1
            else:
                output.append(nal)

            # Keep the next start code so the loop can use it as the current one.
            del self._buf[:next_start]

        return output

    def flush(self) -> list[NALUnit]:
        """Emit the final buffered NAL, if any.  Call at end of stream."""
        first = _find_start(self._buf, 0)
        if first is None:
            self._buf.clear()
            return []
        start, start_code_len = first
        if start > 0:
            del self._buf[:start]
        raw = bytes(self._buf)
        self._buf.clear()
        nal = parse_nal(raw, start_code_len)
        if nal is None:
            self.invalid_nals += 1
            return []
        return [nal]

    def reset(self) -> None:
        self._buf.clear()


class AccessUnitAssembler:
    """Group NAL units into access units using AUD and first-slice flags.

    Non-VCL NALs need slightly different treatment: suffix SEI belongs to the
    picture that just ended, while VPS/SPS/PPS and prefix SEI prepare the next
    picture.  Keeping a pending-prefix buffer avoids attaching parameter sets
    that precede an IDR to the previous picture.
    """

    def __init__(self) -> None:
        self._pending: list[NALUnit] = []
        self._pending_started_at: float | None = None
        self._current: list[NALUnit] = []
        self._current_has_vcl = False
        self._current_started_at: float | None = None
        self.discarded_partial_pictures = 0

    def feed(self, nal: NALUnit, received_at: float) -> list[AccessUnit]:
        output: list[AccessUnit] = []

        if nal.is_aud:
            if self._current_has_vcl:
                output.append(self._finish_current())
            self._append_pending(nal, received_at)
            return output

        if nal.is_vcl:
            if not nal.first_slice_segment_in_pic:
                if self._current_has_vcl:
                    self._current.append(nal)
                else:
                    # A non-first slice with no active picture is a fragment.
                    # Drop any prefix gathered for it as well; otherwise stale
                    # parameter sets/SEI could be glued to the next picture.
                    self._pending.clear()
                    self._pending_started_at = None
                    self.discarded_partial_pictures += 1
                return output

            if self._current_has_vcl:
                output.append(self._finish_current())
            self._current = self._pending
            self._current_started_at = self._pending_started_at
            self._pending = []
            self._pending_started_at = None
            if self._current_started_at is None:
                self._current_started_at = received_at
            self._current.append(nal)
            self._current_has_vcl = True
            return output

        if nal.is_parameter_set or nal.nal_type == 39:
            # VPS/SPS/PPS and prefix SEI prepare the picture that follows.
            self._append_pending(nal, received_at)
        elif self._current_has_vcl:
            # Suffix SEI/filler belongs to the picture that just ended.
            self._current.append(nal)
        else:
            self._append_pending(nal, received_at)
        return output

    def _append_pending(self, nal: NALUnit, received_at: float) -> None:
        if not self._pending:
            self._pending_started_at = received_at
        self._pending.append(nal)

    def _finish_current(self) -> AccessUnit:
        au = AccessUnit(tuple(self._current), self._current_started_at or 0.0)
        self._current = []
        self._current_has_vcl = False
        self._current_started_at = None
        return au

    def flush(self) -> list[AccessUnit]:
        if not self._current_has_vcl:
            self._pending.clear()
            self._pending_started_at = None
            return []
        au = self._finish_current()
        return [au]

    def reset(self) -> None:
        self._pending.clear()
        self._pending_started_at = None
        self._current.clear()
        self._current_has_vcl = False
        self._current_started_at = None


class ParameterSetCache:
    """Keep the latest VPS/SPS/PPS seen in the stream."""

    def __init__(self) -> None:
        self._sets: dict[int, NALUnit] = {}

    def update(self, nal: NALUnit) -> bool:
        if nal.is_parameter_set:
            self._sets[nal.nal_type] = nal
            return True
        return False

    def update_all(self, nals: Iterable[NALUnit]) -> None:
        for nal in nals:
            self.update(nal)

    @property
    def complete(self) -> bool:
        return all(t in self._sets for t in PARAMETER_SET_TYPES)

    @property
    def missing(self) -> tuple[int, ...]:
        return tuple(t for t in PARAMETER_SET_TYPES if t not in self._sets)

    def bootstrap_bytes(self) -> bytes:
        return b"".join(self._sets[t].raw for t in PARAMETER_SET_TYPES if t in self._sets)

    def load_file(self, path: Path | str) -> "ParameterSetCache":
        data = Path(path).read_bytes()
        parser = AnnexBParser()
        nals = parser.feed(data)
        nals.extend(parser.flush())
        self.update_all(nals)
        return self

    def write_file(self, path: Path | str) -> Path:
        """Write the complete VPS/SPS/PPS set as an Annex-B file."""
        if not self.complete:
            raise ValueError("parameter sets are incomplete")
        output = Path(path).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_bytes(self.bootstrap_bytes())
        temporary.replace(output)
        return output

    def snapshot(self) -> dict[str, object]:
        return {
            "complete": self.complete,
            "missing": [NAL_NAMES[t] for t in self.missing],
            "sets": {
                NAL_NAMES[t]: {
                    "present": t in self._sets,
                    "bytes": len(self._sets[t].raw) if t in self._sets else 0,
                }
                for t in PARAMETER_SET_TYPES
            },
        }

    def clear(self) -> None:
        self._sets.clear()


def scan_nals(data: bytes) -> list[NALUnit]:
    """Parse a complete in-memory Annex-B stream."""
    parser = AnnexBParser()
    nals = parser.feed(data)
    nals.extend(parser.flush())
    return nals
