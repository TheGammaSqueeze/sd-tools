#!/usr/bin/env bash
# extract_uefi.sh - Extract and LZMA-decompress the XBL Core UEFI firmware volume
# from uefi.elf, exposing the DXE drivers (including ClockDxe, which holds the
# CPU/clock frequency plan).
#
# Background: on SM6450 the OSM/EPSS CPU clock bring-up is NOT in xbl_s.melf
# (that is only the ~115KB XBL SEC loader) and NOT a plaintext table in
# devcfg/xbl_config. It lives in uefi.elf, a UEFI firmware volume whose main
# body is one LZMA-compressed GUIDed section. This script carves the FV (it
# starts at file offset 0x1000, the _FVH signature is at 0x1028) and runs
# uefi-firmware-parser, which walks the FFS and decompresses the LZMA volume.
#
# Requires: python3 -m pip install uefi_firmware  (provides uefi-firmware-parser)
#
# Usage:
#   extract_uefi.sh [uefi.elf] [outdir]
# Then look for ClockDxe (GUID 4db5dea6-5302-4d1a-8a82-677a683b0d29):
#   find <outdir> -path '*4db5dea6*/section1.pe'
set -euo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
UEFI="${1:-$HERE/stock/firmware/uefi.elf}"
OUT="${2:-$HERE/modified/uefi_ext}"
mkdir -p "$OUT"
python3 -c "d=open('$UEFI','rb').read(); open('$OUT/fv.bin','wb').write(d[0x1000:])"
command -v uefi-firmware-parser >/dev/null || { echo "install: pip install uefi_firmware"; exit 1; }
uefi-firmware-parser -e -O "$OUT" "$OUT/fv.bin" >"$OUT/parse.log" 2>&1 || true
echo "extracted $(find "$OUT" -type f | wc -l) files under $OUT"
clk=$(find "$OUT" -path '*4db5dea6*/section1.pe' 2>/dev/null | head -1)
[ -n "$clk" ] && echo "ClockDxe PE: $clk"
