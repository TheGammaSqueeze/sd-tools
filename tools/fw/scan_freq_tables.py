#!/usr/bin/env python3
"""
scan_freq_tables.py - Heuristic scanner for frequency/voltage tables in Qualcomm
firmware blobs (devcfg.mbn, cpucp.elf, aop.mbn, xbl_config.elf).

This is a RESEARCH aid, not an editor. It looks for monotonic increasing runs of
values under several encodings and reports the ones that look like real DCVS
tables (stepped, not consecutive counters). Byte-alignment coincidences produce
false positives, so every hit must be corroborated (matching a known clock plan,
sitting at a struct boundary, referenced by a nearby string) before it is
trusted. Do NOT edit an offset this tool reports without that corroboration; a
wrong firmware edit can hard-brick the bootloader.

Encodings tried:
  - MHz as u32/u16 little-endian (some AOP/RPMh bus and DDR tables)
  - lval as u8/u16 (EPSS/OSM: frequency as a multiple of the ~19.2 MHz source;
    MHz shown is value*19.2, only meaningful if the multiplier is really 19.2)

Usage:
    scan_freq_tables.py <blob> [--min-step N] [--min-len N]
"""
import sys, struct

XO_MHZ = 19.2


def scan(data, min_step=8, min_len=5):
    hits = []
    encs = [
        ("MHz u32LE", "<I", 300, 3500),
        ("MHz u16LE", "<H", 300, 3500),
        ("lval u8", "B", 15, 175),
        ("lval u16LE", "<H", 15, 175),
    ]
    for name, fmt, lo, hi in encs:
        w = struct.calcsize(fmt)
        run = []
        for i in range(0, len(data) - w, w):
            v = struct.unpack(fmt, data[i:i + w])[0]
            if lo <= v <= hi and (not run or v > run[-1][1]):
                run.append((i, v))
            else:
                _flush(run, name, min_step, min_len, hits)
                run = [(i, v)] if lo <= v <= hi else []
        _flush(run, name, min_step, min_len, hits)
    return hits


def _flush(run, name, min_step, min_len, hits):
    if len(run) < min_len:
        return
    vals = [v for _, v in run]
    step = (vals[-1] - vals[0]) / (len(vals) - 1)
    if step >= min_step:
        hits.append((name, run[0][0], vals, round(step, 1)))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    fn = sys.argv[1]
    min_step = 8
    min_len = 5
    if "--min-step" in sys.argv:
        min_step = int(sys.argv[sys.argv.index("--min-step") + 1])
    if "--min-len" in sys.argv:
        min_len = int(sys.argv[sys.argv.index("--min-len") + 1])
    data = open(fn, "rb").read()
    hits = scan(data, min_step, min_len)
    print(f"# {fn}: {len(hits)} candidate stepped table(s) "
          f"(min_step={min_step}, min_len={min_len})")
    print("# UNCONFIRMED heuristic output; corroborate before trusting any offset.")
    for name, off, vals, step in hits:
        extra = ""
        if "lval" in name:
            extra = "  MHz~" + str([round(v * XO_MHZ) for v in vals[:8]])
        print(f"  {name:10} @{off:#08x} step~{step:<6} {vals[:8]}{'...' if len(vals) > 8 else ''}{extra}")


if __name__ == "__main__":
    main()
