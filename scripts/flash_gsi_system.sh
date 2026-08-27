#!/usr/bin/env bash
# flash_gsi_system.sh - Flash a GammaOS bvN GSI to the system logical partition
# on the CURRENT slot, without touching any other partition or switching slots.
#
# The bvN build is a GSI (Generic System Image, target tdgsi_arm64_ab): a
# system-only image. On this A/B dynamic-partition device the clean, supported
# way to replace system in place is fastbootd (`fastboot flash system`), which:
#   - writes the logical `system` partition of the CURRENT slot (system_a here),
#   - auto-resizes it to fit the new image within super,
#   - does NOT switch the active slot and does NOT touch boot/vendor/vbmeta/etc.
#
# The bootloader is unlocked (verifiedbootstate orange), so AVB is not enforced,
# the modified system boots even though its hash no longer matches vbmeta, so no
# vbmeta edit is needed (that is why "only system" is enough here).
#
# This is the recommended path for a GSI. A recovery-sideload zip is the other
# route (scripts/build_system_ota.sh) but this device's GSI build ships no Edify
# updater, so fastbootd is simpler and more robust.
#
# Usage:
#   flash_gsi_system.sh <system.img|.erofs> [--execute]
# Default is DRY-RUN (prints the commands). --execute runs them (device must be
# reachable). Pass the ext4 .img for maximum compatibility.
set -euo pipefail
IMG="${1:?usage: flash_gsi_system.sh <system.img> [--execute]}"
EXECUTE=0; [ "${2:-}" = "--execute" ] && EXECUTE=1
[ -f "$IMG" ] || { echo "image not found: $IMG"; exit 1; }

CMDS=(
  "fastboot reboot fastboot"                 # enter fastbootd (dynamic partitions)
  "fastboot flash system $IMG"               # current slot, resized, no slot switch
  "fastboot reboot"
)
echo "GSI system flash (current slot, no other partitions, no slot switch)"
echo "image: $IMG ($(du -h "$IMG" | cut -f1))"
if [ "$EXECUTE" -eq 1 ]; then
  command -v fastboot >/dev/null || { echo "fastboot not on PATH"; exit 1; }
  echo "device in fastboot: $(fastboot devices 2>/dev/null | head -1)"
  echo "current slot: $(fastboot getvar current-slot 2>&1 | grep current-slot || true)"
  for c in "${CMDS[@]}"; do echo "+ $c"; $c; done
else
  echo "DRY RUN. Put the device in bootloader (fastboot), then run with --execute, or:"
  printf '  %s\n' "${CMDS[@]}"
  echo
  echo "Notes:"
  echo "  - If 'fastboot flash system' reports 'Not enough space', run first:"
  echo "      fastboot delete-logical-partition product   (or resize; frees super space)"
  echo "  - To revert: fastboot flash system <stock system_a.img> the same way."
fi
