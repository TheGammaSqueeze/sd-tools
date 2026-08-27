#!/usr/bin/env bash
# selftest.sh - Regression-test the sd-tools toolchain against the committed
# stock artifacts. Run after any change to the tools. Exits non-zero on failure.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
DTC="prebuilt/dtc-aosp-x86_64"
pass=0; fail=0
ok()   { echo "  PASS $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL $1"; fail=$((fail+1)); }

echo "[1] AOSP dtc present and reports Android build"
"$DTC" --version 2>/dev/null | grep -q "Android" && ok "dtc-aosp" || bad "dtc-aosp"

echo "[2] split/join round-trips the dtb section byte-for-byte"
tmp=$(mktemp -d)
python3 tools/dtb/split_dtb.py stock/dtb/vendor_boot.dtb-section "$tmp/s" >/dev/null 2>&1
python3 tools/dtb/join_dtb.py "$tmp/s" "$tmp/rejoin" >/dev/null 2>&1
cmp -s stock/dtb/vendor_boot.dtb-section "$tmp/rejoin" && ok "split+join identity" || bad "split+join identity"

echo "[3] all 15 trees survive dtc round-trip as SEMANTIC-MATCH + idempotent"
if tools/dtb/verify_roundtrip.sh stock/dtb/vendor_boot.dtb-section 2>/dev/null \
     | grep -q "SEMANTIC-DIFF\|NON-IDEMPOTENT"; then
  bad "roundtrip fidelity"
else
  n=$(tools/dtb/verify_roundtrip.sh stock/dtb/vendor_boot.dtb-section 2>/dev/null | grep -c SEMANTIC-MATCH)
  [ "$n" -eq 15 ] && ok "roundtrip 15/15" || bad "roundtrip only $n/15"
fi

echo "[4] MBN inspector detects the SecTools test root on ABL"
python3 tools/signing/inspect_mbn.py stock/firmware/abl.elf 2>/dev/null \
  | grep -qi "TEST ROOT" && ok "mbn test-key detect" || bad "mbn test-key detect"

echo "[5] gpu_overclock.sh produces a clean surgical edit (only freq lines change)"
"$DTC" -q -I dtb -O dts stock/dtb/06.dtb -o "$tmp/base.dts" 2>/dev/null
scripts/gpu_overclock.sh stock/dtb/06.dtb 1000 "$tmp/oc.dtb" >/dev/null 2>&1
diffn=$(diff <("$DTC" -q -I dtb -O dts stock/dtb/06.dtb 2>/dev/null) \
             <("$DTC" -q -I dtb -O dts "$tmp/oc.dtb" 2>/dev/null) | grep -c '^[<>]')
[ "$diffn" -eq 4 ] && ok "gpu_overclock surgical (4 lines)" || bad "gpu_overclock changed $diffn lines"

echo "[6] add_gpu_level.py recompiles and adds a level in every bin"
python3 tools/dtb/add_gpu_level.py "$tmp/base.dts" 1000 "$tmp/add.dts" >/dev/null 2>&1
if "$DTC" -q -I dts -O dtb "$tmp/add.dts" -o "$tmp/add.dtb" 2>/dev/null; then
  before=$(grep -c "qcom,gpu-pwrlevel@" "$tmp/base.dts")
  after=$(grep -c "qcom,gpu-pwrlevel@" <("$DTC" -q -I dtb -O dts "$tmp/add.dtb" 2>/dev/null))
  [ "$after" -gt "$before" ] && ok "add_gpu_level (+$((after-before)) nodes)" || bad "add_gpu_level no new nodes"
else
  bad "add_gpu_level recompile"
fi

echo "[6b] remove_gpu_level.py: remove-node recompiles and add/remove is reversible"
python3 tools/dtb/add_gpu_level.py "$tmp/base.dts" 1000 "$tmp/rvadd.dts" >/dev/null 2>&1
python3 tools/dtb/remove_gpu_level.py "$tmp/rvadd.dts" "$tmp/rvrm.dts" --top >/dev/null 2>&1
if "$DTC" -q -I dts -O dtb "$tmp/rvrm.dts" -o "$tmp/rvrm.dtb" 2>/dev/null \
   && cmp -s <("$DTC" -q -I dtb -O dts stock/dtb/06.dtb 2>/dev/null) \
            <("$DTC" -q -I dtb -O dts "$tmp/rvrm.dtb" 2>/dev/null); then
  ok "remove-node valid + add/remove reversible"
else
  bad "remove-node or reversibility"
fi

echo "[7] qtestsign present and importable"
python3 -c "import sys; sys.path.insert(0,'tools/signing/qtestsign'); import mbn" 2>/dev/null \
  && ok "qtestsign import" || bad "qtestsign import"

echo "[7b] re-sign of devcfg/cpucp/aop yields valid ELF, payload byte-preserved"
resign_ok=1
for pair in devcfg:devcfg.mbn cpucp:cpucp.elf aop:aop.mbn; do
  typ=${pair%%:*}; f=${pair##*:}
  scripts/resign_firmware.sh "$typ" "stock/firmware/$f" "$tmp/$f.signed" >/dev/null 2>&1
  [ -f "$tmp/$f.signed" ] || { resign_ok=0; continue; }
  python3 - "stock/firmware/$f" "$tmp/$f.signed" <<'PY' || resign_ok=0
import sys, struct
def loads(fn):
    d=open(fn,'rb').read(); is64=d[4]==2
    if is64: phoff=struct.unpack('<Q',d[32:40])[0]; ent=struct.unpack('<H',d[54:56])[0]; num=struct.unpack('<H',d[56:58])[0]
    else: phoff=struct.unpack('<I',d[28:32])[0]; ent=struct.unpack('<H',d[42:44])[0]; num=struct.unpack('<H',d[44:46])[0]
    out=[]
    for i in range(num):
        o=phoff+i*ent
        if is64: t=struct.unpack('<I',d[o:o+4])[0]; off=struct.unpack('<Q',d[o+8:o+16])[0]; sz=struct.unpack('<Q',d[o+32:o+40])[0]; fl=struct.unpack('<I',d[o+4:o+8])[0]
        else: t=struct.unpack('<I',d[o:o+4])[0]; off=struct.unpack('<I',d[o+4:o+8])[0]; sz=struct.unpack('<I',d[o+16:o+20])[0]; fl=struct.unpack('<I',d[o+24:o+28])[0]
        if t==1 and not (fl & 0xFF000000): out.append(d[off:off+sz])
    return out
sys.exit(0 if loads(sys.argv[1])==loads(sys.argv[2]) else 1)
PY
done
[ "$resign_ok" = 1 ] && ok "firmware re-sign non-destructive" || bad "firmware re-sign"

echo "[8] secp384r1 test keys committed (self-contained signing)"
[ -f tools/signing/testkeys-secp384r1/qpsa_rootca.key ] && ok "test keys present" || bad "test keys missing"

echo "[9] vendored abie matches upstream + the committed patch"
if [ -d third_party/abie ] && ( cd third_party/abie && git apply --reverse --check "$HERE/patches/abie-use-aosp-dtc.patch" ) 2>/dev/null; then
  ok "abie == upstream + patch"
else
  bad "abie/patch mismatch"
fi

echo "[10] sectools + secp384r1 test keys vendored in-repo"
[ -f third_party/sectools/sectools.py ] && ok "sectools vendored" || bad "sectools missing"

echo "[11b] self-built Turnip is loadable (HMI), supports a702, Vulkan-only"
STU=gpu/turnip-selfbuilt/vulkan.turnip.so
hmi=$(readelf -sW "$STU" 2>/dev/null | grep -cw HMI || true)
cxx=$(readelf -d "$STU" 2>/dev/null | grep -c "libc++_shared" || true)
if [ -f "$STU" ] && [ "${hmi:-0}" -ge 1 ] && grep -qa a702 "$STU" && [ "${cxx:-0}" -eq 0 ]; then
  ok "self-built Turnip valid (HMI + a702 + self-contained)"
else
  bad "self-built Turnip missing/regressed"
fi

echo "[11] sectools secimage pipeline imports and runs"
python3 third_party/sectools/sectools.py secimage --help >/dev/null 2>&1 \
  && ok "sectools secimage runs" || bad "sectools secimage broken"

rm -rf "$tmp"
echo
echo "selftest: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
