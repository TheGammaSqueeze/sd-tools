#!/usr/bin/env python3
"""
join_dtb.py - Reassemble a Qualcomm appended-FDT blob from individual .dtb files.

The inverse of split_dtb.py. Each FDT self-describes its size, so reassembly is
a plain in-order concatenation with no header, no padding table and no
alignment. Order MUST match the original split order (00.dtb, 01.dtb, ...),
because the running device selects its tree by index (ro.boot.dtb_idx) as well
as by msm-id, and reordering can change which tree a given index resolves to.

Usage:
    join_dtb.py <indir> <out.dtb>            # joins NN.dtb in numeric order
    join_dtb.py <out.dtb> a.dtb b.dtb ...    # explicit order
"""
import sys, os, glob


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    first = sys.argv[1]
    if os.path.isdir(first):
        out = sys.argv[2]
        files = sorted(glob.glob(os.path.join(first, "*.dtb")))
    else:
        out = first
        files = sys.argv[2:]
    if not files:
        print("no input .dtb files")
        sys.exit(2)
    with open(out, "wb") as w:
        for f in files:
            data = open(f, "rb").read()
            w.write(data)
            print(f"+ {os.path.basename(f)}  {len(data):#x} bytes")
    print(f"\nwrote {out}  ({os.path.getsize(out):#x} bytes, {len(files)} trees)")


if __name__ == "__main__":
    main()
