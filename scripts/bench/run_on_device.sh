#!/usr/bin/env bash
# Host-side: push tools, apply max-perf, run bench, save labelled result.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL="${1:?usage: run_on_device.sh <label> [outdir]}"
OUT="${2:-$HERE/../../bench/results}"; mkdir -p "$OUT"
adb push "$HERE/cpubench" "$HERE/membench" "$HERE/gpubench" "$HERE"/device_*.sh /data/local/tmp/ >/dev/null
adb shell 'chmod 0755 /data/local/tmp/cpubench /data/local/tmp/membench /data/local/tmp/gpubench /data/local/tmp/*.sh'
adb shell 'sh /data/local/tmp/device_setup_maxperf.sh' >/dev/null 2>&1
sleep 2
res="$OUT/${LABEL}.txt"
adb shell 'sh /data/local/tmp/device_run_bench.sh' 2>&1 | tee "$res"
echo "saved $res"
