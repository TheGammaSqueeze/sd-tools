#!/system/bin/sh
# restore stock behavior
set -x
echo 0 > /sys/class/gpio_pwm/duty      # fan off (real node)
setprop persist.gammaos.fan_mode off
pkill -CONT thermal-engine-v2 2>/dev/null; pkill -CONT thermal-engine 2>/dev/null
start vendor.thermal-engine 2>/dev/null; start thermal-engine 2>/dev/null
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  echo walt > $p/scaling_governor 2>/dev/null
  echo $(cat $p/cpuinfo_min_freq) > $p/scaling_min_freq
done
G=/sys/class/kgsl/kgsl-3d0
echo 6 > $G/min_pwrlevel 2>/dev/null; echo 0 > $G/force_clk_on 2>/dev/null; echo 0 > $G/force_bus_on 2>/dev/null
