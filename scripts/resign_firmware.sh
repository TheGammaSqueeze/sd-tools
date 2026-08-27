#!/usr/bin/env bash
# resign_firmware.sh - Re-sign a modified Qualcomm firmware ELF/MBN.
#
# Two backends, chosen by --mode:
#
#   --mode qtestsign   (default) writes a correctly formatted MBN hash segment
#                      with a stub signature. Works ONLY on a device whose
#                      secure-boot fuse is open (this device is very likely such,
#                      see docs/01). Self-contained, no external tree.
#
#   --mode sectools    uses the genuine QTI sectools fetched into external/ by
#                      scripts/setup.sh, producing a real secp384r1 signature
#                      under the committed test keys. Needed only if the device
#                      turns out to be fused to a test root.
#
# The image TYPE maps to the signer group:
#   abl.elf      -> qtestsign "abl"    / sectools "-g appsbl"
#   xbl / sbl    -> qtestsign "xbl"    / sectools "-g xbl"
#   tz.mbn       -> qtestsign "tz"     / sectools "-g tz"
#   hyp/hypvm    -> qtestsign "hyp"    / sectools "-g hyp"
#   devcfg.mbn   ->                       sectools "-g devcfg"   (needed for CPU/DDR OC)
#
# Usage:
#   resign_firmware.sh [--mode qtestsign|sectools] <type> <in.elf> <out.elf> [chipset]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MODE=qtestsign
if [ "${1:-}" = "--mode" ]; then MODE="$2"; shift 2; fi
TYPE="$1"; IN="$2"; OUT="$3"; CHIP="${4:-}"

case "$MODE" in
  qtestsign)
    QT="$HERE/tools/signing/qtestsign/qtestsign.py"
    # Map our type names to qtestsign firmware types (which set SW_ID).
    case "$TYPE" in
      abl|appsbl)   ft=abl ;;
      xbl|sbl|sbl1) ft=sbl1 ;;
      tz|qtee)      ft=tz  ;;
      hyp|hypvm)    ft=hyp ;;
      devcfg)       ft=devcfg ;;
      cpucp)        ft=cpucp ;;
      aop)          ft=aop ;;
      xbl-config|xbl_config) ft=xbl-config ;;
      *) echo "no qtestsign type for '$TYPE'; qtestsign supports abl/sbl1/tz/hyp/devcfg/cpucp/aop/xbl-config"; exit 2 ;;
    esac
    # This device is SB3.0 (ECDSA secp384r1, SHA384 hash); MBN header v6 matches.
    # Override with MBN_VERSION if a specific image needs v7.
    MV="${MBN_VERSION:-6}"
    echo "qtestsign ($ft, MBN v$MV): $IN -> $OUT"
    echo "note: qtestsign writes a stub signature; only boots on a secure-boot-OFF device"
    python3 "$QT" -v "$MV" "$ft" "$IN" -o "$OUT"
    ;;
  sectools)
    ST="$HERE/third_party/sectools/sectools.py"
    [ -f "$ST" ] || { echo "sectools missing; run scripts/setup.sh"; exit 1; }
    [ -n "$CHIP" ] || { echo "sectools mode needs the chipset arg (e.g. parrot/6450)"; exit 2; }
    CFG="$HERE/third_party/sectools/config/$CHIP/${CHIP}_secimage.xml"
    echo "sectools ($TYPE) with $CFG"
    python3 "$ST" secimage -i "$IN" -g "$TYPE" -c "$CFG" \
      --cfg_selected_signer qti_presigned --sign -o "$(dirname "$OUT")/"
    echo "sectools writes into $(dirname "$OUT")/<sign_id>/ ; move the signed image to $OUT"
    ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac
echo "done. Verify with: tools/signing/inspect_mbn.py $OUT"
