#!/usr/bin/env bash
# setup.sh - Fetch and build the external tools sd-tools depends on.
#
# We do not vendor the large third-party trees (sectools is ~270MB, the boot
# image editor pulls a Gradle/Kotlin toolchain). This script clones and builds
# them into ./external so the repo stays small. The small, load-bearing pieces
# (the AOSP dtc binary, the secp384r1 test keys, our own scripts) ARE committed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/external"
mkdir -p "$EXT"

echo "== AOSP dtc (the DTB round-trip compiler) =="
if [ ! -x "$ROOT/prebuilt/dtc-aosp-x86_64" ]; then
  git clone --depth 1 -b standalone https://github.com/xzr467706992/dtc-aosp.git "$EXT/dtc-aosp"
  make -C "$EXT/dtc-aosp" NO_PYTHON=1 dtc
  cp "$EXT/dtc-aosp/dtc" "$ROOT/prebuilt/dtc-aosp-x86_64"
fi
"$ROOT/prebuilt/dtc-aosp-x86_64" --version

echo "== cfig Android_boot_image_editor (unpack/repack boot + vendor_boot) =="
[ -d "$EXT/abie" ] || git clone --depth 1 https://github.com/cfig/Android_boot_image_editor.git "$EXT/abie"

echo "== qtestsign (stub MBN signer; works on secure-boot-OFF / unfused parts) =="
[ -d "$ROOT/tools/signing/qtestsign" ] || \
  git clone --depth 1 https://github.com/msm8916-mainline/qtestsign.git "$ROOT/tools/signing/qtestsign"

echo "== sectools v2 from CodeLinaro (genuine QTI signer + secp384r1 test keys) =="
if [ ! -d "$EXT/qccsdk/sectools" ]; then
  git clone --depth 1 -b fermion.iot.1.1.r1-rel \
    https://git.codelinaro.org/clo/le/qccsdk/oss/qccsdkmain.git "$EXT/qccsdk"
fi
echo "sectools at: $EXT/qccsdk/sectools/sectools.py"

echo
echo "setup complete. See docs/ for the workflows."
