#!/usr/bin/env bash
# patch_recovery_adb.sh - Make recovery adb keyless + root by patching the
# recovery ramdisk props (and, for user builds, sepolicy -> permissive), then
# repack. Same approach as /work/airx RECOVERY_FASTBOOTD_ADB_RUNBOOK.md FIX 2.
#
# What it sets in the recovery ramdisk /prop.default:
#   ro.secure=0          adbd runs as root automatically (no `adb root` needed)
#   ro.adb.secure=0      no adb-authorization prompt (recovery cannot show one)
#   ro.debuggable=1      enables adb root / debug
#   security.perf_harden=0
#
# On a `user` recovery, init forces SELinux enforcing and adbd's shell service
# SIGABRTs ("Could not set SELinux context ... u:r:su:s0"); that build also needs
# /sepolicy patched to permissive (magiskpolicy "permissive *"). A `userdebug`
# recovery (ro.debuggable already 1) does not, the props alone give root adb.
# Pass --sepolicy <magiskpolicy> to also apply the permissive patch.
#
# Repack uses the vendored patched abie (AOSP dtc); AVB footer stays NONE
# (unsigned), which boots on an unlocked device without touching vbmeta.
#
# Usage:
#   patch_recovery_adb.sh <recovery.img> <out_recovery.img> [--sepolicy <magiskpolicy>]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
IN="${1:?usage: patch_recovery_adb.sh <recovery.img> <out.img> [--sepolicy magiskpolicy]}"
OUT="${2:?output path required}"
MAGISKPOLICY=""; [ "${3:-}" = "--sepolicy" ] && MAGISKPOLICY="${4:-}"
ABIE="${ABIE_DIR:-$HERE/third_party/abie}"
export AOSP_DTC="${AOSP_DTC:-$HERE/prebuilt/dtc-aosp-x86_64}"

cp "$IN" "$ABIE/recovery.img"
( cd "$ABIE" && rm -rf build/unzip_boot && ./gradlew -q unpack --console=plain >/dev/null 2>&1 )
P="$ABIE/build/unzip_boot/root/prop.default"
[ -f "$P" ] || { echo "no prop.default in recovery ramdisk"; exit 1; }

sed -i 's/^ro.secure=1/ro.secure=0/' "$P"
sed -i 's/^security.perf_harden=1/security.perf_harden=0/' "$P"
grep -q '^ro.debuggable=1' "$P" || sed -i '1a ro.debuggable=1' "$P"
grep -q '^ro.adb.secure=' "$P" || sed -i '/^ro.debuggable=1/a ro.adb.secure=0' "$P"

if [ -n "$MAGISKPOLICY" ]; then
  SEP="$ABIE/build/unzip_boot/root/sepolicy"
  [ -f "$SEP" ] && { echo "sepolicy -> permissive"; "$MAGISKPOLICY" --load "$SEP" --save "$SEP" "permissive *"; }
fi

echo "patched props:"; grep -nE "^ro.secure|^ro.adb.secure|^ro.debuggable|^security.perf_harden" "$P"
( cd "$ABIE" && ./gradlew -q pack --console=plain >/dev/null 2>&1 )
cp "$ABIE/recovery.img" "$OUT"
echo "wrote $OUT"
echo "make a flashable OTA:  scripts/build_flash_ota.sh --out rec.zip --part recovery:$OUT:physical --slot \$(active slot)"
echo "or fastbootd:          fastboot flash recovery $OUT"
