#!/usr/bin/env bash
# RG 55G1 overclock campaign orchestrator (host-side).
#
# Runs the two campaign modes against the device and saves labelled, parseable
# results so baseline and each overclock step can be compared:
#   (A) COMBINED all-max stress: GPU + both CPU clusters + MEM pinned to max
#       simultaneously, fan max, thermal off, sustained.
#   (B) PER-COMPONENT bench: CPU big / CPU little / MEM / GPU each measured.
#
# The device must be online with root adb. Fan is driven by the real gpio-pwm
# node inside device_setup_maxperf.sh (the persist.gammaos.fan_mode prop is dead
# on the GSI); thermal-engine is stopped there too.
#
# Usage:
#   campaign.sh run   <label> [combined_seconds]   # push, setup, per-comp + combined
#   campaign.sh table                              # regenerate the docs/14 results table
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RESROOT="$HERE/../../bench/results"
DUR="${3:-120}"

push_tools() {
  adb push "$HERE/cpubench" "$HERE/membench" "$HERE/gpubench" "$HERE"/device_*.sh /data/local/tmp/ >/dev/null
  adb shell 'chmod 0755 /data/local/tmp/cpubench /data/local/tmp/membench /data/local/tmp/gpubench /data/local/tmp/*.sh'
}

cmd_run() {
  local label="${1:?usage: campaign.sh run <label> [seconds]}"
  local out="$RESROOT/$label"; mkdir -p "$out"
  echo "== $label: waiting for device =="
  adb wait-for-device
  push_tools
  echo "== applying max-perf (fan max, thermal off, pin max OPP) =="
  adb shell 'sh /data/local/tmp/device_setup_maxperf.sh' 2>&1 | tee "$out/setup.txt" >/dev/null
  sleep 2
  echo "== (B) per-component bench =="
  adb shell 'sh /data/local/tmp/device_run_bench.sh' 2>&1 | tee "$out/percomponent.txt"
  echo "== (A) combined all-max stress ${DUR}s =="
  adb shell "sh /data/local/tmp/device_combined_stress.sh $DUR" 2>&1 | tee "$out/combined.txt"
  echo "== state snapshot =="
  adb shell 'G=/sys/class/kgsl/kgsl-3d0
    echo gpu_avail=$(cat $G/gpu_available_frequencies)
    echo fan_duty=$(cat /sys/class/gpio_pwm/duty 2>/dev/null) fan_rpm=$(cat /sys/class/gpio_pwm/speed 2>/dev/null)' 2>&1 | tee "$out/state.txt"
  echo "saved $out/"
}

cmd_table() {
  python3 "$HERE/parse_bench.py" "$RESROOT"
}

case "${1:-}" in
  run)   shift; cmd_run "$@";;
  table) cmd_table;;
  *) echo "usage: campaign.sh {run <label> [seconds] | table}"; exit 1;;
esac
