#!/usr/bin/env python3
"""Overclock the Adreno GPU on the RG 55G1 (RavelinP) by extending the
gfx3d clock frequency table inside gpucc-ravelin.ko.

Why this and not the DTB: adding a GPU pwrlevel to the device tree makes
kgsl advertise the frequency, but clk_rcg2 round_rate clamps any request to
the highest freq_tbl entry it finds, and that table lives in the module, not
the DTB. So a DTB-only 1100 MHz rounds back down to the stock 1010 MHz entry.
The gfx3d RCG is clk_rcg2_ops fed by a clk_alpha_pll_lucid_evo (fractional,
arbitrary set_rate), so appending higher entries genuinely raises the clock.

Table layout (symbol ftbl_gpu_cc_gx_gfx3d_clk_src, in .rodata): 24-byte stride
per entry: u64 freq, u8 src, u8 pre_div, u16 m, u16 n, then 8 trailing bytes.
The stock entries use src=0x03, pre_div=0x03 (post-divide by 2), m=n=0. Stock
top entry is 1010 MHz. A zero-freq entry terminates the table.

Module signing is off on this device (CONFIG_MODULE_SIG unset, sig_enforce=0),
so a byte-patched module loads. Deployment must survive dm-verity on
vendor_dlkm: disable verification on the WHOLE vbmeta chain (top vbmeta AND
vbmeta_system, not just the slot flags avbctl toggles) before booting to
system, or recompute the vendor_dlkm hashtree and re-sign vbmeta.

Usage:
  gpucc_oc.py <gpucc-ravelin.ko> <out.ko> --freqs 1050 1100 1150 1200
Requires llvm-readelf/llvm-objcopy (set LLVM_BIN or have them on PATH).
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
    ap.add_argument("--freqs", nargs="+", type=int, required=True,
                    help="MHz values to append, e.g. 1050 1100 1150 1200")
    args = ap.parse_args()

    data = bytearray(open(args.infile, "rb").read())
    base = rodata_file_offset(args.infile) + symbol_rodata_offset(args.infile)

    off, last = base, None
    while True:
        freq, = struct.unpack_from("<Q", data, off)
        if freq == 0:
            break
        last = freq
        off += STRIDE
    print(f"stock top entry: {last} Hz; terminator at file 0x{off:x}")

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
