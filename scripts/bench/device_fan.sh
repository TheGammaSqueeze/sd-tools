#!/system/bin/sh
# device fan control. The RG 55G1 fan is a gpio-pwm (gpio-pwm.ko), NOT the dead
# persist.gammaos.fan_mode prop. Control: /sys/class/gpio_pwm/duty 0-255 (255=max).
# /sys/class/gpio_pwm/speed is the tachometer RPM readout (read-only).
D=/sys/class/gpio_pwm
v=${1:-255}
echo "$v" > $D/duty
sleep 1
echo "fan duty=$(cat $D/duty) rpm=$(cat $D/speed)"
