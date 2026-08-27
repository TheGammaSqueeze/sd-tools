#!/usr/bin/env python3
"""
split_dtb.py - Split a Qualcomm appended-FDT blob into individual .dtb files.

Qualcomm boot/vendor_boot images store multiple device trees (one per SoC
variant / silicon revision) simply concatenated together. There is no QCDT
header table on modern parts; the bootloader picks the matching FDT at runtime
by comparing qcom,msm-id / qcom,board-id inside each tree.

We split the same way KonaBess does: scan for the FDT magic D0 0D FE ED and use
each FDT's own totalsize field (big-endian u32 at magic+4) to advance to the
next tree. This never mis-splits on a d00dfeed byte pattern that happens to sit
inside a tree's payload.

Usage:
    split_dtb.py <blob> <outdir>

Writes <outdir>/NN.dtb for each tree and prints an index with the /model string.
"""
import sys, os, struct

MAGIC = b"\xd0\x0d\xfe\xed"


def find_trees(data):
    offs = []
    i = 0
    n = len(data)
    while True:
        i = data.find(MAGIC, i)
        if i < 0:
            break
        if i + 8 > n:
            break
        totalsize = struct.unpack(">I", data[i + 4:i + 8])[0]
        # Sanity: a valid FDT totalsize must fit and be non-trivial.
        if totalsize < 0x40 or i + totalsize > n:
            i += 4
            continue
        offs.append((i, totalsize))
        i += totalsize
    return offs


def model_of(blob):
    # Cheap /model extraction without a full FDT parser: the property value is a
    # NUL-terminated string somewhere in the strings/struct block. We just look
    # for a "Qualcomm Technologies" marker, which every base tree carries.
    m = blob.find(b"Qualcomm Technologies")
    if m < 0:
        return "?"
    end = blob.find(b"\x00", m)
    return blob[m:end].decode("ascii", "replace")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    blob = open(sys.argv[1], "rb").read()
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    trees = find_trees(blob)
    if not trees:
        print("no FDT magic found; not an appended-DTB blob")
        sys.exit(2)
    for n, (off, size) in enumerate(trees):
        piece = blob[off:off + size]
        path = os.path.join(outdir, f"{n:02d}.dtb")
        open(path, "wb").write(piece)
        print(f"{n:02d}.dtb  off={off:#010x} size={size:#x}  {model_of(piece)}")
    print(f"\n{len(trees)} device trees written to {outdir}")


if __name__ == "__main__":
    main()
