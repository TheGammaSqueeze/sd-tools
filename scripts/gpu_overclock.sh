#!/usr/bin/env bash
# gpu_overclock.sh - Raise the top GPU pwrlevel frequency in one device tree.
#
# Pure DTB edit (no firmware re-sign needed on this device). It rewrites the top
# qcom,gpu-freq of every speed-bin's pwrlevel@0 to the requested MHz, leaving the
# RPMh voltage corner (qcom,level) and ACD at their stock TURBO values. See
# docs/04-overclocking-research.md for the ceiling and the risks, and for how to
# ADD a new level instead of raising the existing top.
#
# Usage:
#   gpu_overclock.sh <stock.dtb> <MHz> <out.dtb>
# Example:
#   gpu_overclock.sh stock/dtb/06.dtb 1000 modified/dtb/06.parrot.gpu1000.dtb
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DTC="${AOSP_DTC:-$HERE/prebuilt/dtc-aosp-x86_64}"
SRC="$1"; MHZ="$2"; OUT="$3"
[ -x "$DTC" ] || { echo "AOSP dtc missing (run scripts/setup.sh)"; exit 1; }

t="$(mktemp -d)"
$DTC -q -I dtb -O dts "$SRC" -o "$t/in.dts"

# Current top freq = the highest qcom,gpu-freq value in the tree.
top_hex=$(grep -oE 'qcom,gpu-freq = <0x[0-9a-fA-F]+>' "$t/in.dts" \
          | grep -oE '0x[0-9a-fA-F]+' | sort -u \
          | python3 -c 'import sys; print(max(sys.stdin, key=lambda x:int(x,16)).strip())')
new_hex=$(python3 -c "print(hex($MHZ*1000000))")

python3 - "$t/in.dts" "$top_hex" "$new_hex" <<'PY'
import sys
f,old,new=sys.argv[1:4]
s=open(f).read()
n=s.count(f"qcom,gpu-freq = <{old}>")
s=s.replace(f"qcom,gpu-freq = <{old}>", f"qcom,gpu-freq = <{new}>")
open(f,'w').write(s)
print(f"replaced {n} top-level entr{'y' if n==1 else 'ies'}: {old} -> {new}")
PY

$DTC -q -I dts -O dtb "$t/in.dts" -o "$OUT"
echo "wrote $OUT"
echo "diff vs stock (should be only the freq lines):"
diff <($DTC -q -I dtb -O dts "$SRC" 2>/dev/null) <($DTC -q -I dtb -O dts "$OUT" 2>/dev/null) || true
rm -rf "$t"
