#!/usr/bin/env bash
# epss_lut.sh - Read (and optionally write) the live EPSS CPU frequency LUT on a
# booted SM6450/SM4375 device over adb. This is the practical CPU-overclock route
# on this platform, because the operating-point table is not a static editable
# blob in the shipped firmware (see docs/06, docs/07): it is composed at boot and
# latched into the EPSS hardware FREQ_LUT / VOLT_LUT registers.
#
# Register model (Linux qcom-cpufreq-hw driver):
#   domain base:   domain0 = 0x17d91000, domain1 = 0x17d92000
#   FREQ_LUT[i]  = base + 0x100 + i*4     ; lval = reg & 0xFFF ; freq_kHz = lval*19200
#                                           src  = (reg >> 30) & 0x3
#   VOLT_LUT[i]  = base + 0x200 + i*4     ; corner/vc in low bits
#   up to ~40 rows; the table ends when the freq stops incrementing.
#
# Reads use devmem (busybox) or a devmem2 binary on the device; both need root
# AND /dev/mem. NOTE: on the RG 55G1 GammaOS Next Lite GSI /dev/mem is compiled
# out (CONFIG_DEVMEM unset), so both fail here; the runtime route on this device
# needs a kernel module doing ioremap instead (module signing is off). See docs/07.
# WRITES ARE EXPERIMENTAL: the EPSS may re-latch or ignore a runtime LUT change,
# and a freq above the CPRh voltage envelope can hang the CPU. Read first.
#
# Usage:
#   epss_lut.sh dump [0|1]                 # dump domain 0 (default) or 1
#   epss_lut.sh write <domain> <row> <lval>   # EXPERIMENTAL, root, at your risk
#
# Requires: adb with a rooted device (adb root / su).
set -euo pipefail
XO_KHZ=19200
dom_base() { [ "${1:-0}" = "1" ] && echo 0x17d92000 || echo 0x17d91000; }

adb_su() { adb shell "su -c '$*' 2>/dev/null || $*"; }

read32() { # phys_addr -> hex value, via devmem then devmem2
  local a="$1"
  adb_su "devmem $a 2>/dev/null || devmem2 $a w 2>/dev/null" \
    | grep -oiE '0x[0-9a-f]+' | tail -1
}

dump() {
  local dom="${1:-0}" base; base="$(dom_base "$dom")"
  echo "EPSS domain $dom base $base"
  printf "%-4s %-12s %-6s %-9s %-8s\n" row FREQ_LUT lval freq_MHz VOLT_LUT
  local i last=0
  for i in $(seq 0 39); do
    local foff voff fv vv lval mhz
    foff=$(printf '0x%x' $((base + 0x100 + i*4)))
    voff=$(printf '0x%x' $((base + 0x200 + i*4)))
    fv=$(read32 "$foff" || true); vv=$(read32 "$voff" || true)
    [ -n "${fv:-}" ] || { echo "(no read at row $i; need root/devmem)"; break; }
    lval=$(( fv & 0xFFF )); mhz=$(( lval * XO_KHZ / 1000 ))
    [ "$lval" -eq 0 ] && break
    [ "$mhz" -lt "$last" ] && break
    printf "%-4s %-12s %-6s %-9s %-8s\n" "$i" "$fv" "$lval" "$mhz" "${vv:-?}"
    last=$mhz
  done
}

write() {
  local dom="$1" row="$2" lval="$3" base; base="$(dom_base "$dom")"
  local foff; foff=$(printf '0x%x' $((base + 0x100 + row*4)))
  local cur; cur=$(read32 "$foff")
  # keep the source/other bits, replace only the low 12 bits (lval)
  local newv; newv=$(printf '0x%x' $(( (cur & ~0xFFF) | (lval & 0xFFF) )) )
  echo "EXPERIMENTAL: domain $dom row $row $foff: $cur -> lval $lval (freq $((lval*XO_KHZ/1000)) MHz)"
  echo "writing $newv (Ctrl-C now to abort)"; sleep 3
  adb_su "devmem $foff w $newv 2>/dev/null || devmem2 $foff w $newv"
  echo "done; re-dump to confirm"
}

cmd="${1:-dump}"; shift || true
case "$cmd" in
  dump)  dump "${1:-0}" ;;
  write) write "$1" "$2" "$3" ;;
  *) grep '^#' "$0" | sed 's/^# \{0,1\}//' ;;
esac
