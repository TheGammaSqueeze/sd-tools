#!/usr/bin/env bash
# make_disabled_vbmeta.sh - Produce a vbmeta image that disables AVB verification.
#
# The top-level vbmeta.img on this package IS signed (SHA256_RSA4096, flags=0,
# enforced) and hashes boot/vendor_boot/etc. Flashing a modified vendor_boot
# changes its hash, so stock vbmeta would reject it. We do not have the OEM
# RSA4096 private key, so we cannot re-sign vbmeta with the real hashes.
#
# The supported route on an unlocked bootloader is a vbmeta whose header carries
# the VERIFICATION_DISABLED flag (0x2). When present the bootloader skips AVB for
# the whole slot, so the modified vendor_boot boots. This needs the bootloader
# unlocked (fastboot flashing unlock); a locked bootloader ignores the flag.
#
# Usage:
#   make_disabled_vbmeta.sh <out.img>
#
# Then: fastboot --disable-verity --disable-verification flash vbmeta <out.img>
# (the avbtool flag and the fastboot flags are belt-and-braces; either disables).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
AVB="${AVBTOOL:-$HERE/external/abie/aosp/avb/avbtool.v1.2.py}"
OUT="$1"
[ -f "$AVB" ] || { echo "avbtool not found at $AVB (run scripts/setup.sh)"; exit 1; }

# flags 2 = AVB_VBMETA_IMAGE_FLAGS_VERIFICATION_DISABLED. An empty unsigned
# vbmeta with this flag disables verification for the whole set.
python3 "$AVB" make_vbmeta_image --flags 2 --padding_size 4096 --output "$OUT"
echo "wrote $OUT (verification-disabled vbmeta)"
python3 "$AVB" info_image --image "$OUT" 2>/dev/null | grep -iE "Flags|Algorithm|Header" || true
