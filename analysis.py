
from pathlib import Path
from collections import Counter

raw = Path("vt13_idle.bin").read_bytes()

# 根据当前样本观察到的候选帧标识
known_types = {0xF5, 0xF6, 0xF8}

def is_header(pos):
    return (
        pos + 4 <= len(raw)
        and raw[pos] in known_types
        and raw[pos + 1] == 0x64
    )

frames = []
position = 0
skipped = 0
aligned = 0

while position + 4 <= len(raw):
    if not is_header(position):
        position += 1
        skipped += 1
        continue

    length = int.from_bytes(
        raw[position + 2:position + 4], "little"
    )

    if not (8 <= length <= 4096):
        position += 1
        skipped += 1
        continue

    end = position + length
    if end > len(raw):
        break

    if is_header(end):
        aligned += 1

    frames.append((
        position,
        raw[position],
        length,
        raw[position:end]
    ))

    position = end

print("Total bytes:", len(raw))
print("Parsed frames:", len(frames))
print("Boundary matches:", aligned)
print("Skipped bytes:", skipped)

print("\nFrame types:")
for typ, count in Counter(f[1] for f in frames).items():
    print(f"  0x{typ:02X}: {count}")

print("\nFrame lengths:")
for length, count in Counter(f[2] for f in frames).most_common(15):
    print(f"  {length:4d} bytes: {count}")

print("\nFirst 20 frames:")
for offset, typ, length, payload in frames[:20]:
    print(
        f"offset={offset:8d} "
        f"type=0x{typ:02X} "
        f"length={length:4d} "
        f"data={payload[:24].hex(' ')}"
    )
