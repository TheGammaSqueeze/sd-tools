#!/usr/bin/env bash
# flash_gpu_oc.sh - End-to-end GPU overclock: repack vendor_boot, build a
# verification-disabled vbmeta, and flash both over fastboot.
#
# Default is DRY-RUN: it builds the images and PRINTS the fastboot commands
# without running them. Pass --execute to actually flash (device must be in
# fastboot/bootloader mode and unlocked). This is the pure-DTB GPU overclock, so
# no firmware re-sign is involved (see docs for CPU/DDR, which need re-sign).
#
# Usage:
#   flash_gpu_oc.sh <stock_vendor_boot.img> <family> <MHz> [--addlevel] [--execute]
#     family: parrot | ravelin | montague
#
# Example (dry run):
#   flash_gpu_oc.sh /mnt/c/55g1/.../vendor_boot.img parrot 1000
# Example (flash for real):
#   flash_gpu_oc.sh /mnt/c/55g1/.../vendor_boot.img parrot 1000 --execute
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$1"; FAMILY="$2"; MHZ="$3"; shift 3
ADDLVL=""; EXECUTE=0
for a in "$@"; do
  case "$a" in
    --addlevel) ADDLVL="--addlevel" ;;
    --execute)  EXECUTE=1 ;;
  esac
done

OUTDIR="$HERE/modified/firmware"
mkdir -p "$OUTDIR"
VB_OUT="$OUTDIR/vendor_boot.$FAMILY.gpu$MHZ.img"
VBMETA_OUT="$OUTDIR/vbmeta.disabled.img"

echo "== 1. repack vendor_boot with GPU $MHZ MHz ($FAMILY) =="
"$HERE/scripts/repack_vendor_boot.sh" "$IMG" "$FAMILY" "$MHZ" "$VB_OUT" $ADDLVL

echo "== 2. verify the edit is present and all trees valid =="
tmp="$(mktemp -d)"
python3 "$HERE/tools/dtb/split_dtb.py" "$VB_OUT" "$tmp" >/dev/null
# Robust check: count the new frequency as a big-endian u32 across the whole
# image (each edited tree contributes at least one occurrence per speed-bin).
occ=$(python3 - "$VB_OUT" "$MHZ" <<'PY'
import sys, struct
d=open(sys.argv[1],'rb').read()
print(d.count(struct.pack('>I', int(sys.argv[2])*1000000)))
PY
)
if [ "$occ" -gt 0 ]; then
  echo "  edit present ($MHZ MHz appears $occ time(s))"
else
  echo "  WARNING: edit not found in repacked image"
fi
# every tree must still be a valid FDT
bad=0
for d in "$tmp"/*.dtb; do
  "$HERE/prebuilt/dtc-aosp-x86_64" -q -I dtb -O dts "$d" -o /dev/null 2>/dev/null || bad=$((bad+1))
done
n=$(ls "$tmp"/*.dtb | wc -l)
echo "  $n device trees, $((n-bad)) valid"
rm -rf "$tmp"

echo "== 3. build verification-disabled vbmeta =="
AVBTOOL="${AVBTOOL:-$HERE/third_party/abie/aosp/avb/avbtool.v1.2.py}"
"$HERE/scripts/make_disabled_vbmeta.sh" "$VBMETA_OUT" >/dev/null
echo "  $VBMETA_OUT"

echo "== 4. flash =="
CMDS=(
  "fastboot flash vbmeta $VBMETA_OUT"
  "fastboot flash vbmeta_system $VBMETA_OUT"
  "fastboot flash vendor_boot $VB_OUT"
  "fastboot reboot"
)
if [ "$EXECUTE" -eq 1 ]; then
  command -v fastboot >/dev/null || { echo "fastboot not on PATH"; exit 1; }
  echo "  device (must be unlocked): $(fastboot devices 2>/dev/null | head -1)"
  for c in "${CMDS[@]}"; do echo "  + $c"; $c; done
else
  echo "  DRY RUN. To flash, unlock the bootloader then run with --execute, or run:"
  printf '    %s\n' "${CMDS[@]}"
  echo "  (flash the active slot, or append _a/_b to target a specific slot)"
fi
echo
echo "restore stock with: scripts/restore_stock.sh <stock_vendor_boot.img>"
