
from pathlib import Path
from collections import Counter, defaultdict

raw = Path("vt13_idle.bin").read_bytes()
TYPES = {0xF5, 0xF6, 0xF8}

def u16(buf, offset):
    return int.from_bytes(buf[offset:offset+2], "little")

def u32(buf, offset):
    return int.from_bytes(buf[offset:offset+4], "little")

def is_header(pos):
    return (
        pos + 4 <= len(raw)
        and raw[pos] in TYPES
        and raw[pos+1] == 0x64
    )

frames = []
pos = 0
skipped = 0

while pos + 20 <= len(raw):
    if not is_header(pos):
        pos += 1
        skipped += 1
        continue

    total_len = u16(raw, pos + 2)
    end = pos + total_len

    if not (20 <= total_len <= 4096) or end > len(raw):
        pos += 1
        skipped += 1
        continue

    # Only accept a frame if its end aligns
    # with the next recognized header or EOF.
    if end != len(raw) and not is_header(end):
        pos += 1
        skipped += 1
        continue

    frames.append(raw[pos:end])
    pos = end

print("Valid candidate frames:", len(frames))
print("Skipped bytes:", skipped)

by_type = defaultdict(list)
for f in frames:
    by_type[f[0]].append(f)

for typ, group in sorted(by_type.items()):
    print(f"\n=== Type 0x{typ:02X} ===")
    print("Frame count:", len(group))

    # Test total_len - inner_len
    header_sizes = Counter(
        len(f) - u16(f, 18) for f in group
    )
    print("Candidate header sizes:")
    for size, count in header_sizes.most_common(10):
        print(f"  {size} bytes: {count}")

    # Candidate message ID at offsets 16-17
    msg_ids = Counter(u16(f, 16) for f in group)
    print("Top candidate message IDs:")
    for msg, count in msg_ids.most_common(15):
        print(f"  0x{msg:04X}: {count}")

    # Candidate timestamp / sequence at offsets 4-7
    values = [u32(f, 4) for f in group]
    diffs = Counter(
        (b - a) & 0xFFFFFFFF
        for a, b in zip(values, values[1:])
    )

    print("Offset 4 sequence differences:")
    print(diffs.most_common(10))

    # Show frames inconsistent with the main hypothesis
    expected = 20 if typ == 0xF5 else 24
    anomalies = [
        f for f in group
        if len(f) - u16(f, 18) != expected
    ]

    print("Header-length anomalies:", len(anomalies))
    for f in anomalies[:3]:
        print("  ", f[:32].hex(" "))




from collections import Counter

def u16(b, offset):
    return int.from_bytes(
        b[offset:offset + 2], "little"
    )

f6 = [f for f in frames if f[0] == 0xF6]

anomalies = [
    f for f in f6
    if len(f) - u16(f, 18) != 24
]

print("\n=== F6 anomaly analysis ===")
print("Total:", len(anomalies))

# Group by frame length and candidate identifiers
signatures = Counter(
    (
        len(f),
        u16(f, 14),
        u16(f, 16),
        u16(f, 18),
    )
    for f in anomalies
)

for (length, field14, field16, field18), count in \
        signatures.most_common(20):
    print(
        f"count={count:4d} "
        f"length={length:4d} "
        f"field14=0x{field14:04X} "
        f"field16=0x{field16:04X} "
        f"field18=0x{field18:04X}"
    )

# Check whether 0xC451 is associated with anomalies
c451 = [
    f for f in f6 if u16(f, 16) == 0xC451
]

print("\n0xC451 messages:", len(c451))
print(
    "0xC451 anomalies:",
    sum(len(f) - u16(f, 18) != 24 for f in c451)
)

print("\nFirst 5 anomaly frames:")
for f in anomalies[:5]:
    print(f.hex(" "))
