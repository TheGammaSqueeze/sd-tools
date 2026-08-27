# Keyless, root adb in recovery (RG 55G1)

Goal: use adb in recovery without authorizing a key ("without setting vendor
keys") and get a root shell there. Same fix as the Qualcomm handheld runbook at
`/work/airx/RECOVERY_FASTBOOTD_ADB_RUNBOOK.md` (FIX 2), adapted to this device.

## What controls it

Recovery reads its own `/prop.default` from the recovery ramdisk. adb behaviour
there is gated by three props:
- `ro.secure` = 1 makes adbd refuse root.
- `ro.adb.secure` = 1 makes adbd require an authorized RSA key (which recovery
  cannot prompt for, so adb sits "unauthorized").
- `ro.debuggable` enables `adb root` / debug.

This device's stock recovery is already `ro.build.type=userdebug` with
`ro.debuggable=1` and `ro.secure=1` (no `ro.adb.secure` line). So it is simpler
than the airx case (a `user` recovery that also needed sepolicy patched to
permissive): here the prop patch alone gives keyless root adb.

## The patch

`scripts/patch_recovery_adb.sh <recovery.img> <out.img>` unpacks the recovery
ramdisk (vendored patched abie, AOSP dtc), sets in `/prop.default`:

```
ro.secure=0
ro.adb.secure=0
ro.debuggable=1
security.perf_harden=0
```

and repacks (AVB footer NONE, unsigned, boots on the unlocked bootloader without
touching vbmeta). Verified round-trip: the repacked image re-unpacks with those
exact values.

If the recovery were a `user` build (it is not here), the shell service would
SIGABRT under enforcing SELinux and you would also pass `--sepolicy
<magiskpolicy>` to mark the ramdisk `/sepolicy` permissive.

## Build a flashable OTA

```
scripts/build_flash_ota.sh --out recovery-adb-debuggable.zip \
  --part recovery:<patched recovery.img>:physical --slot _a
```

The zip is testkey-signed (whole-file, what recovery verifies) and writes only
`recovery_a`, no slot switch, no other partition. Flash it either way:

```
# recovery sideload (sideload mode does not need an authorized key):
adb reboot recovery ; adb sideload recovery-adb-debuggable.zip
# or fastbootd:
adb reboot fastboot ; fastboot flash recovery <patched recovery.img>
```

Then `adb reboot recovery` and check:

```
adb shell 'getprop ro.secure; getprop ro.adb.secure; id'
# expect 0 / 0 / uid=0(root)
```

## Caveats

- Version match: the recovery.img here comes from the `V3.0_debug` package; the
  unit runs retail `V3.0.8`. Recovery is isolated (kernel from boot.img, modules
  from vendor_boot, both device-matched), so it should boot, but the safest path
  is to patch the device's OWN recovery: pull it (`dd if=$(readlink -f
  /dev/block/by-name/recovery_a) of=/sdcard/rec.img` from a root shell, or via
  the OTA) and run the patch on that. Recovery is separate from the boot path, so
  a bad recovery does not stop normal boot, revert by flashing the stock
  recovery.img the same way.
- Do both slots (`--slot _a` and `_b`) if you want it to survive a slot change.
