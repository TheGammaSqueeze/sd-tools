#!/system/bin/sh
# COMBINED stress: hammer CPU (both clusters), GPU, and MEM at the SAME time,
# for DUR seconds, then report sustained clocks + peak temp + whether all
# workers survived (stability). Run after device_setup_maxperf.sh.
T=/data/local/tmp
DUR=${1:-60}
maxtemp(){ m=0; for z in /sys/class/thermal/thermal_zone*/temp; do v=$(cat $z 2>/dev/null); [ "$v" -gt "$m" ] 2>/dev/null && m=$v; done; echo $m; }
echo "combined_stress dur=${DUR}s temp_before=$(maxtemp)"
# background workers (loop for the duration)
( end=$(( $(date +%s)+DUR )); while [ $(date +%s) -lt $end ]; do taskset f0 $T/cpubench 100000000 1 >/dev/null 2>&1 || echo "CPU_BIG_FAIL"; done ) &
P1=$!
( end=$(( $(date +%s)+DUR )); while [ $(date +%s) -lt $end ]; do taskset 0f $T/cpubench 60000000 1 >/dev/null 2>&1 || echo "CPU_LITTLE_FAIL"; done ) &
P2=$!
( end=$(( $(date +%s)+DUR )); while [ $(date +%s) -lt $end ]; do $T/membench 256 >/dev/null 2>&1 || echo "MEM_FAIL"; done ) &
P3=$!
( end=$(( $(date +%s)+DUR )); while [ $(date +%s) -lt $end ]; do $T/gpubench 32768 8192 1 >/dev/null 2>&1 || echo "GPU_FAIL"; done ) &
P4=$!
# sample clocks/temps mid-run
sleep $(( DUR/2 ))
echo "mid: cpu_big=$(cat /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq) cpu_lil=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq) gpu=$(cat /sys/class/kgsl/kgsl-3d0/gpuclk) gpu_busy=$(cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage 2>/dev/null) temp=$(maxtemp)"
wait $P1 $P2 $P3 $P4
echo "combined_stress done temp_after=$(maxtemp)"
