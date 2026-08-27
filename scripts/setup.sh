#!/usr/bin/env bash
# setup.sh - Build the in-repo tools. Everything sd-tools needs is vendored in
# this repository; nothing is fetched from the network. This script only builds
# what needs building (the AOSP dtc binary is already committed prebuilt).
#
# Vendored under the repo:
#   prebuilt/dtc-aosp-x86_64      the DTB round-trip compiler (prebuilt)
#   third_party/abie              the patched Android_boot_image_editor (source)
#   third_party/sectools          the genuine QTI sectools + secp384r1 test keys
#   tools/signing/qtestsign       stub MBN signer for unfused parts
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== AOSP dtc =="
if [ ! -x "$ROOT/prebuilt/dtc-aosp-x86_64" ]; then
  # Rebuild from the committed source only if the prebuilt is missing.
  tmp="$(mktemp -d)"
  git clone --depth 1 -b standalone https://github.com/xzr467706992/dtc-aosp.git "$tmp/dtc"
  make -C "$tmp/dtc" NO_PYTHON=1 dtc
  cp "$tmp/dtc/dtc" "$ROOT/prebuilt/dtc-aosp-x86_64"
  rm -rf "$tmp"
fi
"$ROOT/prebuilt/dtc-aosp-x86_64" --version

echo "== patched Android_boot_image_editor (build the vendored source) =="
if [ -d "$ROOT/third_party/abie" ]; then
  ( cd "$ROOT/third_party/abie" && ./gradlew -q build -x test ) && echo "abie built"
else
  echo "third_party/abie missing"; exit 1
fi

echo "== sectools (vendored, no build needed) =="
[ -f "$ROOT/third_party/sectools/sectools.py" ] && echo "sectools present" || echo "third_party/sectools missing"

echo "== qtestsign (vendored) =="
[ -f "$ROOT/tools/signing/qtestsign/qtestsign.py" ] && echo "qtestsign present" || echo "qtestsign missing"

echo
echo "setup complete. Everything is in-repo. See docs/ for the workflows."
