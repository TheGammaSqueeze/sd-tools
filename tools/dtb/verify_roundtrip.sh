#!/usr/bin/env bash
# verify_roundtrip.sh - Prove a Qualcomm DTB survives a dtc decompile/recompile.
#
# True byte-for-byte identity with the vendor blob is NOT achievable through any
# dtc: the vendor toolchain merges the string table (short property names stored
# as suffixes of longer ones), and dtc lays the string table out differently.
# That changes string offsets, hence the struct block bytes, hence the file.
#
# The guarantee that actually matters for booting is SEMANTIC identity: the
# recompiled DTB must describe the exact same tree. We prove that by decompiling
# both the stock DTB and the recompiled DTB and requiring the two DTS texts to be
# identical. If they match, the device parses them identically. We also confirm
# the pipeline is idempotent (a second recompile is byte-stable).
#
# Usage:
#   verify_roundtrip.sh <file.dtb>
#   verify_roundtrip.sh <appended-blob>      # auto-splits and checks every tree
set -euo pipefail
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
DTC="${AOSP_DTC:-$HERE/prebuilt/dtc-aosp-x86_64}"
[ -x "$DTC" ] || { echo "AOSP dtc not found at $DTC (run scripts/setup.sh)"; exit 1; }

check_one() {
  local src="$1" tag="$2"
  local t; t="$(mktemp -d)"
  "$DTC" -q -I dtb -O dts "$src"       -o "$t/stock.dts"
  "$DTC" -q -I dts -O dtb "$t/stock.dts" -o "$t/rt1.dtb"
  "$DTC" -q -I dtb -O dts "$t/rt1.dtb"  -o "$t/rt1.dts"
  "$DTC" -q -I dts -O dtb "$t/rt1.dts"  -o "$t/rt2.dtb"
  local os rs sem idem
  os=$(stat -c%s "$src"); rs=$(stat -c%s "$t/rt1.dtb")
  if cmp -s "$t/stock.dts" "$t/rt1.dts"; then sem="SEMANTIC-MATCH"; else sem="SEMANTIC-DIFF"; fi
  if cmp -s "$t/rt1.dtb" "$t/rt2.dtb"; then idem="idempotent"; else idem="NON-IDEMPOTENT"; fi
  printf "%-28s stock=%-7d recompiled=%-7d (%+d)  %s  %s\n" \
         "$tag" "$os" "$rs" "$((rs-os))" "$sem" "$idem"
  rm -rf "$t"
  [ "$sem" = "SEMANTIC-MATCH" ] || return 1
}

f="$1"
magics=$(grep -c $'\xd0\x0d\xfe\xed' "$f" 2>/dev/null || true)
if python3 "$HERE/tools/dtb/split_dtb.py" "$f" /tmp/_vrt_split >/dev/null 2>&1 && \
   [ "$(ls /tmp/_vrt_split/*.dtb 2>/dev/null | wc -l)" -gt 1 ]; then
  echo "appended blob: checking each tree"
  rc=0
  for d in /tmp/_vrt_split/*.dtb; do check_one "$d" "$(basename "$d")" || rc=1; done
  rm -rf /tmp/_vrt_split
  exit $rc
else
  check_one "$f" "$(basename "$f")"
fi
