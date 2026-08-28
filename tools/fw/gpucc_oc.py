#!/usr/bin/env python3
"""Overclock the Adreno GPU on the RG 55G1 (RavelinP) by raising the top entry
of the gfx3d clock frequency table inside gpucc-ravelin.ko.

Why this and not the DTB: kgsl clamps to the highest freq_tbl entry, and that
table lives in the module, not the DTB. The gfx3d RCG is clk_rcg2_ops fed by a
clk_alpha_pll_lucid_evo (fractional PLL), so the table entry sets the achievable
rate; a DTB-only pwrlevel rounds back down to the stock 1010 MHz entry.

Table layout (symbol ftbl_gpu_cc_gx_gfx3d_clk_src, in .rodata): 24-byte stride
per entry: u64 freq, u8 src, u8 pre_div, u16 m, u16 n, then 8 trailing bytes.
Stock entries use src=0x03, pre_div=0x03 (post-divide by 2), m=n=0. Stock top
entry is 1010 MHz. A zero-freq entry terminates the table.

DO NOT APPEND ENTRIES. Device-confirmed: growing the table (writing new entries
into the trailing zero padding) kernel-panics at module load inside
__clk_register / qcom_cc_really_probe / gpucc_ravelin_probe (a data abort from a
garbage pointer built out of an injected freq value). A bisection proved the
repack itself is fine: the unmodified module via the same debugfs repack boots.
The SAFE method is --in-place: change ONLY the existing top entry's 8-byte freq
value, keeping the entry count and layout identical. KGSL then picks up the new
rate directly (no DTB edit needed). NOTE: on this unit 1050/1100 boot and clock
but are not stable under sustained load at the stock voltage corner (SoC resets),
so a stable OC beyond 1010 needs a GMU ACD / voltage-corner change too. See
docs/14.

Module signing is off (CONFIG_MODULE_SIG unset, sig_enforce=0), so a byte-patched
module loads. Deployment must bypass dm-verity on vendor_dlkm (permissive +
avb-stripped fstab boot images, or recompute the hashtree); see docs/14.

Usage:
  gpucc_oc.py <in.ko> <out.ko> --in-place 1100    # SAFE: raise top entry to 1100
  gpucc_oc.py <in.ko> <out.ko> --freqs 1050 1100  # DANGEROUS: appends, panics probe
Requires llvm-readelf/llvm-nm (set LLVM_BIN or have them on PATH).
"""
import argparse, os, struct, subprocess, sys

SYMBOL = "ftbl_gpu_cc_gx_gfx3d_clk_src"
STRIDE = 24
SRC, PRE_DIV = 0x03, 0x03  # matches every stock entry on this SoC


def _tool(name):
    b = os.environ.get("LLVM_BIN", "")
    cand = os.path.join(b, name) if b else name
    return cand


def rodata_file_offset(ko):
    out = subprocess.check_output([_tool("llvm-readelf"), "-S", ko], text=True)
    for line in out.splitlines():
        # [ N] .rodata PROGBITS <addr> <fileoff> <size> ...
        parts = line.replace("[", " ").replace("]", " ").split()
        if ".rodata" in parts:
            i = parts.index(".rodata")
            # addr, off are the two hex fields after PROGBITS
            return int(parts[i + 3], 16)
    raise SystemExit("could not find .rodata section")


def symbol_rodata_offset(ko):
    out = subprocess.check_output([_tool("llvm-nm"), ko], text=True)
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 3 and cols[2] == SYMBOL:
            return int(cols[0], 16)
    raise SystemExit(f"symbol {SYMBOL} not found")


def entry(freq):
    b = bytearray(STRIDE)
    struct.pack_into("<Q", b, 0, freq)
    b[8] = SRC
    b[9] = PRE_DIV
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--in-place", type=int, metavar="MHz",
                   help="SAFE: raise the existing top entry to this MHz (no new entries)")
    g.add_argument("--freqs", nargs="+", type=int,
                   help="DANGEROUS: append these MHz entries (panics probe at module load)")
    args = ap.parse_args()

    data = bytearray(open(args.infile, "rb").read())
    base = rodata_file_offset(args.infile) + symbol_rodata_offset(args.infile)

    off, last, last_off = base, None, None
    while True:
        freq, = struct.unpack_from("<Q", data, off)
        if freq == 0:
            break
        last = freq
        last_off = off
        off += STRIDE
    print(f"stock top entry: {last} Hz at file 0x{last_off:x}; terminator at 0x{off:x}")

    if args.in_place is not None:
        # change only the 8-byte freq of the existing top entry, layout unchanged
        struct.pack_into("<Q", data, last_off, args.in_place * 1_000_000)
        open(args.outfile, "wb").write(data)
        print(f"in-place: top entry -> {args.in_place} MHz; size {len(data)} (unchanged); "
              f"wrote {args.outfile}")
        return

    new = [f * 1_000_000 for f in args.freqs]
    need = (len(new) + 1) * STRIDE  # entries + a fresh terminator
    if any(data[off + i] for i in range(need)):
        raise SystemExit("no zero padding after the table; aborting to avoid clobber")

    p = off
    for hz in new:
        data[p:p + STRIDE] = entry(hz)
        p += STRIDE
    open(args.outfile, "wb").write(data)
    print(f"appended {len(new)} entries up to {max(new)} Hz; wrote {args.outfile}")


if __name__ == "__main__":
    main()
