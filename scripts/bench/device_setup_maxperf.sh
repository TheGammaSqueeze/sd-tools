#!/system/bin/sh
# Run ON DEVICE (root). Pin everything to max OPP, fan max, thermal off.
set -x
# fan to max (GammaOS fan service reads this prop)
setprop persist.gammaos.fan_mode max
# stop thermal throttling
for s in vendor.thermal-engine thermal-engine vendor.thermal.chg-cdev vendor.thermal-hal-2-0 thermal@2.0; do stop $s 2>/dev/null; done
pkill -STOP thermal-engine-v2 2>/dev/null
pkill -STOP thermal-engine 2>/dev/null
# CPU: performance governor + pin min=max on both clusters
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  mx=$(cat $p/cpuinfo_max_freq)
  echo performance > $p/scaling_governor
  echo $mx > $p/scaling_max_freq
  echo $mx > $p/scaling_min_freq
done
# GPU: pin to fastest pwrlevel (0), force clocks on, perf governor
G=/sys/class/kgsl/kgsl-3d0
echo performance > $G/devfreq/governor 2>/dev/null
echo 0 > $G/max_pwrlevel; echo 0 > $G/min_pwrlevel
echo 1 > $G/force_clk_on 2>/dev/null
echo 1 > $G/force_bus_on 2>/dev/null
echo 1000000 > $G/idle_timer 2>/dev/null
# report
echo "=== state ==="
for p in /sys/devices/system/cpu/cpufreq/policy*; do echo "$p gov=$(cat $p/scaling_governor) cur=$(cat $p/scaling_cur_freq) max=$(cat $p/scaling_max_freq)"; done
echo "GPU cur=$(cat $G/gpuclk) max=$(cat $G/max_gpuclk) minlvl=$(cat $G/min_pwrlevel) maxlvl=$(cat $G/max_pwrlevel)"
getprop persist.gammaos.fan_mode
