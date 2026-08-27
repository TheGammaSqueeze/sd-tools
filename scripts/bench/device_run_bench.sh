#!/system/bin/sh
# Run ON DEVICE (root). Runs the CPU (both clusters) + MEM benchmarks and reports
# clocks + temps. Assumes device_setup_maxperf.sh already applied. Emits parseable
# key=value lines.
T=/data/local/tmp
maxtemp(){ m=0; for z in /sys/class/thermal/thermal_zone*/temp; do v=$(cat $z 2>/dev/null); [ "$v" -gt "$m" ] 2>/dev/null && m=$v; done; echo $m; }
echo "run_ts=$(date +%s)"
echo "temp_before_mC=$(maxtemp)"
echo "cpu_big_maxkhz=$(cat /sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq)"
echo "cpu_little_maxkhz=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_max_freq)"
echo "gpu_maxhz=$(cat /sys/class/kgsl/kgsl-3d0/max_gpuclk)"
echo -n "CPU_BIG "; taskset f0 $T/cpubench 200000000 5
echo -n "CPU_LITTLE "; taskset 0f $T/cpubench 120000000 5
echo -n "MEM "; taskset f0 $T/membench 256
echo -n "GPU "; $T/gpubench 32768 8192 4
echo "cpu_big_cur=$(cat /sys/devices/system/cpu/cpufreq/policy6/scaling_cur_freq)"
echo "gpu_cur=$(cat /sys/class/kgsl/kgsl-3d0/gpuclk)"
echo "temp_after_mC=$(maxtemp)"
