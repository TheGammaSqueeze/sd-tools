#!/usr/bin/env bash
# build_updater.sh - Build the arm64 Edify `updater` (the recovery update-binary)
# from a LineageOS/AOSP tree, and vendor it at prebuilt/update-binary-arm64.
#
# The GammaOS bvN GSI product sets target_recovery=false and does not ship an
# updater, but the `updater` module itself still compiles for the product. This
# builds just that target and copies the ELF into the repo so build_flash_ota.sh
# is self-contained.
#
# Usage:  TREE=/path/to/aosp-tree LUNCH=lineage_arm64_bvN-ap2a-userdebug build_updater.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TREE="${TREE:-/work/GammaOSNextDistribution-A14}"
LUNCH="${LUNCH:-lineage_arm64_bvN-ap2a-userdebug}"
[ -f "$TREE/build/envsetup.sh" ] || { echo "no AOSP tree at $TREE (set TREE=)"; exit 1; }

cd "$TREE"
# shellcheck disable=SC1091
source build/envsetup.sh >/dev/null 2>&1
lunch "$LUNCH" >/dev/null 2>&1 || { echo "lunch $LUNCH failed; try another release (ap1a/ap2a/...)"; exit 1; }
m updater

SRC=$(find out/target/product -name updater -path "*system*bin*" 2>/dev/null | head -1)
[ -n "$SRC" ] || SRC=$(find out -name updater -path "*EXECUTABLES*" ! -name "*.toc" 2>/dev/null | head -1)
[ -f "$SRC" ] || { echo "updater not found after build"; exit 1; }
mkdir -p "$HERE/prebuilt"
cp "$SRC" "$HERE/prebuilt/update-binary-arm64"
chmod 0755 "$HERE/prebuilt/update-binary-arm64"
file "$HERE/prebuilt/update-binary-arm64"
echo "vendored -> prebuilt/update-binary-arm64"
