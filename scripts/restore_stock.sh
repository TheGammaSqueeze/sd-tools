#!/usr/bin/env bash
# restore_stock.sh - Print (or run) the fastboot commands to restore stock boot
# chain images after an overclock experiment. Dry-run by default.
#
# Usage:
#   restore_stock.sh <stock_vendor_boot.img> [stock_vbmeta.img] [--execute]
#
# The firmware stock images live in stock/firmware/. Restoring a slot means
# flashing the stock image back to the same partition label (see docs/05).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VB="$1"; shift || true
VBMETA=""; EXECUTE=0
for a in "$@"; do
  case "$a" in
    --execute) EXECUTE=1 ;;
    *) VBMETA="$a" ;;
  esac
done
FW="$HERE/stock/firmware"

CMDS=( "fastboot flash vendor_boot $VB" )
[ -n "$VBMETA" ] && CMDS+=( "fastboot flash vbmeta $VBMETA" )
# Firmware partitions (both slots) from the committed stock images.
declare -A MAP=(
  [abl]="$FW/abl.elf" [xbl]="$FW/xbl_s.melf" [xbl_config]="$FW/xbl_config.elf"
  [devcfg]="$FW/devcfg.mbn" [cpucp]="$FW/cpucp.elf" [aop]="$FW/aop.mbn"
)
for part in "${!MAP[@]}"; do
  f="${MAP[$part]}"
  [ -f "$f" ] || continue
  CMDS+=( "fastboot flash ${part}_a $f" "fastboot flash ${part}_b $f" )
done
CMDS+=( "fastboot reboot" )

if [ "$EXECUTE" -eq 1 ]; then
  command -v fastboot >/dev/null || { echo "fastboot not on PATH"; exit 1; }
  for c in "${CMDS[@]}"; do echo "+ $c"; $c; done
else
  echo "DRY RUN. Restore commands (run with --execute to apply):"
  printf '  %s\n' "${CMDS[@]}"
fi
