# Refresh-rate-switch flicker (RG 55G1 / RavelinP)

Symptom: the panel flickers when it leaves the idle 60 fps mode for another
refresh rate.

## Most likely cause

On Qualcomm SDE/DPU displays, refresh-rate modes are grouped. Two modes in the
SAME group differ only in the vertical front porch (VFP), so switching between
them is seamless (the DPU just retimes, no visible glitch). Two modes in
DIFFERENT groups require a full DSI mode-set, the panel is effectively re-
initialised, which shows as a flicker. A flicker specifically on leaving the idle
60 fps state is the classic signature of a cross-group (non-seamless) switch, or
of the panel's idle/low-power state exiting with a mode-set.

`scripts/diag_display.sh` collects the evidence over adb (no root needed for most
of it): the `DisplayMode` list with the `group=` field, the SF refresh-rate
policy (`DesiredDisplayModeSpecs`, `allowGroupSwitching`), and the vendor refresh
/ idle props. If the 60 fps mode and the target mode report different `group=`
values, that is the flicker.

## Fixes, least invasive first

1. Lock the refresh rate so it never crosses groups (user-space, reversible, no
   flashing):
   ```
   adb shell settings put system min_refresh_rate 60
   adb shell settings put system peak_refresh_rate 60
   ```
   (or pin both to 90 if 90 is the preferred rate). This trades adaptive refresh
   for a flicker-free fixed rate. Some builds also expose
   `settings put global game_driver_... ` and a developer-options "peak refresh".

2. Let SurfaceFlinger switch within a group only: confirm
   `allowGroupSwitching` and the primary/appRequest ranges in `dumpsys display`;
   constraining the app-request range to one group avoids the disruptive switch.

3. Panel-side fix in the device tree (needs a vendor/dtbo rebuild + reflash, and
   the real RG 55G1 panel node, which is not in the generic V3.0_debug dtbo, that
   only carries the QTI "Simulator" panels at 60/90/120). Put all rates in one
   mode-group driven by VFP:
   ```
   qcom,mdss-dsi-pan-enable-dynamic-fps;
   qcom,mdss-dsi-pan-fps-update = "dfps_immediate_porch_mode_vfp";
   ```
   with every `qcom,mdss-dsi-timing` sharing horizontal timing and pixel clock so
   only the VFP differs. This makes 60<->N seamless. It requires the retail
   panel dtsi; pull it from the device's own dtbo (`/dev/block/by-name/dtbo`) or
   the retail OTA, edit with the AOSP dtc (docs/02), repack and flash.

## Status

Pending live data: adb dropped mid-recon. Re-run `scripts/diag_display.sh` once
the device is reconnected to confirm the group mismatch and pick the fix. The
generic debug package does not contain the retail panel node, so option 3 needs
the device's own dtbo.
