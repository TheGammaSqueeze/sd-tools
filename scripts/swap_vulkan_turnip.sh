#!/usr/bin/env bash
# swap_vulkan_turnip.sh - Replace the system Vulkan driver with Mesa Turnip,
# COMPLETELY (system-wide), by rewriting the vendor ext4 image so that
# /vendor/lib64/hw/vulkan.adreno.so IS the Turnip binary.
#
# The Android Vulkan loader opens the driver by path (ro.hardware.vulkan=adreno
# -> /vendor/lib64/hw/vulkan.adreno.so) and calls its HMI hwvulkan module. Turnip
# built for Android exports HMI (verified), needs only standard libs, and handles
# Gralloc4, so putting it at that path makes it the system Vulkan driver for every
# app. GLES/EGL stays on the Qualcomm blobs (ro.hardware.egl=adreno).
#
# Turnip is ~13MB larger than the blob and the stock vendor ext4 is nearly full,
# so the image is grown first. The stock file's SELinux context
# (u:object_r:same_process_hal_file:s0) and mode 0644 are restored, without them
# apps are denied dlopen of the driver.
#
# Usage:
#   swap_vulkan_turnip.sh <vendor.img> <vulkan.turnip.so> <out_vendor.img>
#
# Then flash (bootloader unlocked, fastbootd resizes the dynamic partition):
#   scripts/make_disabled_vbmeta.sh vbmeta.disabled.img
#   fastboot --disable-verity --disable-verification flash vbmeta vbmeta.disabled.img
#   fastboot reboot fastboot                       # enter fastbootd (dynamic partitions)
#   fastboot flash vendor <out_vendor.img>
#   fastboot reboot
#
# Requires: e2fsprogs (resize2fs, e2fsck, debugfs).
set -euo pipefail
SRC="$1"; DRV="$2"; OUT="$3"
GROW_MB="${GROW_MB:-28}"
CTX="u:object_r:same_process_hal_file:s0"
TARGET="/lib64/hw/vulkan.adreno.so"   # path inside the vendor fs (vendor is the fs root)

cp "$SRC" "$OUT"
cur=$(stat -c%s "$OUT")
truncate -s $((cur + GROW_MB*1024*1024)) "$OUT"
e2fsck -fy "$OUT" >/dev/null 2>&1 || true
resize2fs "$OUT" >/dev/null 2>&1

tmp="$(mktemp)"; cp "$DRV" "$tmp"
debugfs -w "$OUT" >/dev/null 2>&1 <<EOF
rm $TARGET
write $tmp $TARGET
set_inode_field $TARGET mode 0100644
ea_set $TARGET security.selinux "${CTX}\000"
EOF
rm -f "$tmp"

e2fsck -fy "$OUT" >/dev/null 2>&1 || true
sz=$(debugfs -R "stat $TARGET" "$OUT" 2>/dev/null | grep -oE "Size: [0-9]+" | head -1)
ctx=$(debugfs -R "ea_get $TARGET security.selinux" "$OUT" 2>/dev/null | tr -d '\0')
echo "swapped: $TARGET now $sz, context $ctx"
echo "wrote $OUT ($(stat -c%s "$OUT") bytes)"
echo
echo "On-device alternative (userdebug, unlocked, much simpler, no reflash):"
echo "  adb root && adb remount"
echo "  adb shell cp /vendor/lib64/hw/vulkan.adreno.so /vendor/lib64/hw/vulkan.adreno.so.bak"
echo "  adb push $(basename "$DRV") /vendor/lib64/hw/vulkan.adreno.so"
echo "  adb shell restorecon /vendor/lib64/hw/vulkan.adreno.so && adb reboot"
