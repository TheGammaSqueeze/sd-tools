#!/usr/bin/env bash
# diag_display.sh - Diagnose refresh-rate-switch flicker on the RG 55G1 (adb, no
# root needed for most of this).
#
# Symptom: flicker when the display leaves the idle 60 fps mode for another rate.
# On Qualcomm SDE/DPU displays this is almost always a NON-SEAMLESS mode switch:
# if the refresh-rate modes sit in different "groups", changing rate does a full
# DSI mode-set (panel re-init) which flickers, whereas modes in the SAME group
# switch by only changing the vertical front porch (seamless, no flicker).
#
# This script collects the evidence to confirm that and points at the fix.
set -uo pipefail
run() { echo "### $*"; adb shell "$@" 2>&1; echo; }

echo "===== device ====="
run 'getprop ro.product.model; getprop ro.sf.lcd_density; getprop ro.soc.model'

echo "===== display modes (look at the group= field: differing groups = flicker) ====="
# Each DisplayMode line shows id, resolution, refreshRate and group. Modes that
# share a group switch seamlessly; a rate change across groups re-inits the panel.
adb shell dumpsys SurfaceFlinger 2>&1 | grep -iE "DisplayMode|activeMode|refreshRate|group" | head -40

echo "===== refresh-rate policy (min/peak/default) ====="
adb shell dumpsys display 2>&1 | grep -iE "mRefreshRate|DesiredDisplayModeSpecs|defaultMode|allowGroupSwitching|primaryRanges|appRequest" | head -30

echo "===== SF / vendor refresh + idle props ====="
adb shell getprop 2>&1 | grep -iE "refresh|min_refresh|peak_refresh|smart_panel|idle_time|dfps|vsync|use_content_detection" | head -40

echo "===== panel driver: dfps mode + supported timings (needs the panel node) ====="
# vfp = seamless dynamic fps; anything else (hfp/clock) is more disruptive.
adb shell 'cat /sys/class/drm/*/modes 2>/dev/null | sort -u' 2>&1 | head
adb shell 'for f in /sys/class/backlight/*/ /sys/class/drm/card0-DSI-1/; do echo "$f"; done' 2>&1 | head

echo
echo "INTERPRETATION:"
echo "- If the 60 and non-60 modes have DIFFERENT group= values, the switch is not"
echo "  seamless and that is the flicker. Fixes, in order of least invasive:"
echo "  1. Lock the rate: Settings or 'settings put system peak_refresh_rate 60'"
echo "     and 'min_refresh_rate 60' (or 90/90) so it never crosses groups."
echo "  2. Allow group switching in the SF policy (allowGroupSwitching), only helps"
echo "     if the panel can actually do it seamlessly."
echo "  3. Panel-side (DTB/dtbo): put all rates in one mode-group with vfp-based"
echo "     qcom,mdss-dsi-pan-enable-dynamic-fps + qcom,mdss-dsi-pan-fps-update="
echo "     dfps_immediate_porch_mode_vfp, so only the porch changes on switch."
