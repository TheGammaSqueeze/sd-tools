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
    # qtestsign fw type names: aboot/abl, xbl, tz, hyp
    case "$TYPE" in
      abl|appsbl) ft=abl ;;
      xbl|sbl)    ft=xbl ;;
      tz|qtee)    ft=tz  ;;
      hyp|hypvm)  ft=hyp ;;
      *) echo "qtestsign has no group for '$TYPE'; use --mode sectools"; exit 2 ;;
    esac
    echo "qtestsign ($ft): $IN -> $OUT"
    python3 "$QT" "$ft" "$IN" -o "$OUT"
    ;;
  sectools)
    ST="$HERE/external/qccsdk/sectools/sectools.py"
    [ -f "$ST" ] || { echo "sectools missing; run scripts/setup.sh"; exit 1; }
    [ -n "$CHIP" ] || { echo "sectools mode needs the chipset arg (e.g. parrot/6450)"; exit 2; }
    CFG="$HERE/external/qccsdk/sectools/config/$CHIP/${CHIP}_secimage.xml"
    echo "sectools ($TYPE) with $CFG"
    python3 "$ST" secimage -i "$IN" -g "$TYPE" -c "$CFG" \
      --cfg_selected_signer qti_presigned --sign -o "$(dirname "$OUT")/"
    echo "sectools writes into $(dirname "$OUT")/<sign_id>/ ; move the signed image to $OUT"
    ;;
  *) echo "unknown mode $MODE"; exit 2 ;;
esac
echo "done. Verify with: tools/signing/inspect_mbn.py $OUT"
