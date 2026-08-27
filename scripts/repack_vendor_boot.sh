#!/usr/bin/env bash
# repack_vendor_boot.sh - End-to-end GPU-overclock repack of vendor_boot.img.
#
# Uses the patched Android_boot_image_editor (AOSP dtc) to unpack vendor_boot,
# applies a GPU frequency edit to the chosen SoC family's device trees, and
# repacks a flashable vendor_boot.img. Validated on this package: the repacked
# image re-extracts to 15 valid FDTs with the edit present.
#
# This edits ONLY the DTB, which is not in the secure-boot chain on this device,
# so no firmware re-sign is needed. It does change the vendor_boot AVB hash; see
# docs/02 (vbmeta is unsigned on this package).
#
# Usage:
#   repack_vendor_boot.sh <vendor_boot.img> <family> <MHz> <out.img> [--addlevel]
#     family: parrot | ravelin | montague | all
#     --addlevel: insert a new top level (add_gpu_level.py) instead of raising
#                 the existing top (default).
#
# Prereq: scripts/setup.sh has cloned+patched external/abie and it is built.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
IMG="$1"; FAMILY="$2"; MHZ="$3"; OUT="$4"; MODE="${5:-}"
ABIE="${ABIE_DIR:-$HERE/external/abie}"
export AOSP_DTC="${AOSP_DTC:-$HERE/prebuilt/dtc-aosp-x86_64}"

# Parrot=04-08, Montague=00-03, Ravelin=09-14.
case "$FAMILY" in
  parrot)   idx="04 05 06 07 08" ;;
  montague) idx="00 01 02 03" ;;
  ravelin)  idx="09 10 11 12 13 14" ;;
  all)      idx=$(seq -w 0 14) ;;
  *) echo "unknown family $FAMILY"; exit 2 ;;
esac

[ -d "$ABIE" ] || { echo "abie not found at $ABIE (run scripts/setup.sh)"; exit 1; }
cp "$IMG" "$ABIE/vendor_boot.img"
( cd "$ABIE" && rm -rf build/unzip_boot && ./gradlew -q unpack )

newhex=$(python3 -c "print(hex($MHZ*1000000))")
for i in $idx; do
  dts="$ABIE/build/unzip_boot/dtb.$((10#$i)).dts"
  [ -f "$dts" ] || continue
  if [ "$MODE" = "--addlevel" ]; then
    python3 "$HERE/tools/dtb/add_gpu_level.py" "$dts" "$MHZ" "$dts.new" && mv "$dts.new" "$dts"
  else
    top=$(grep -oE 'qcom,gpu-freq = <0x[0-9a-fA-F]+>' "$dts" | grep -oE '0x[0-9a-fA-F]+' \
          | sort -u | python3 -c 'import sys;print(max(sys.stdin,key=lambda x:int(x,16)).strip())')
    sed -i "s/qcom,gpu-freq = <$top>/qcom,gpu-freq = <$newhex>/g" "$dts"
  fi
  echo "edited dtb.$((10#$i))"
done

( cd "$ABIE" && ./gradlew -q pack )
cp "$ABIE/vendor_boot.img" "$OUT"
echo "wrote $OUT"
echo "verify: tools/dtb/split_dtb.py $OUT /tmp/chk && dtc on /tmp/chk/*.dtb"
