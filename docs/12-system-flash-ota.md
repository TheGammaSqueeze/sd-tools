# Flashing a GammaOS bvN system to the current slot (no slot switch)

Goal: replace the `system` logical partition with the latest non-TV **bvN** build
from `out/home/build-output`, touching no other partition and not switching the
active slot.

## What the build is

`out/home/build-output/lineage-21.0-<date>-UNOFFICIAL-arm64_bvN.img` is a **GSI**
(target `tdgsi_arm64_ab`), a system-only image. `.img` is raw ext4, `.erofs` is
the smaller read-only erofs of the same build. Latest non-TV bvN at time of
writing: `lineage-21.0-20260817-UNOFFICIAL-arm64_bvN.img` (use the `.img`; the
`tv_arm64_bvN` ones are the TV variant, skip them).

`system` is a logical partition inside `super`, so "flashing system" means
rewriting one dynamic partition on the current slot (`system_a`), which fastbootd
resizes to fit. The bootloader is unlocked (recon: `verifiedbootstate orange`),
so AVB is not enforced and the modified system boots without editing vbmeta,
that is why touching only `system` is sufficient.

## Recommended: fastbootd (tested, robust)

For a GSI this is the correct, supported path. It writes the current slot, does
not switch slots, and touches nothing else.

```
scripts/flash_gsi_system.sh out/home/build-output/lineage-21.0-20260817-UNOFFICIAL-arm64_bvN.img
# review the printed commands, then:
scripts/flash_gsi_system.sh <...>.img --execute
```

which runs:

```
fastboot reboot fastboot            # enter fastbootd (dynamic partitions)
fastboot flash system <bvN>.img     # current slot, auto-resized, no slot switch
fastboot reboot
```

If `Not enough space`, free super first (e.g. `fastboot delete-logical-partition
product`). Revert by flashing the stock `system_a.img` the same way.

## As requested: a recovery-sideload zip signed with the key

The device's recovery verifies flashed zips against the AOSP **testkey** (docs/01
and `keys/`, the single cert in the device `otacerts.zip`). `scripts/build_system_ota.sh`
assembles a testkey-signed Edify zip that resizes the current-slot `system` and
writes the image, with no `set_active` (no slot switch):

```
scripts/build_system_ota.sh \
  --img out/home/build-output/lineage-21.0-20260817-UNOFFICIAL-arm64_bvN.img \
  --updater <arm64 Edify updater> \
  --out gammaos-bvN-system.zip
# then: adb reboot recovery ; adb sideload gammaos-bvN-system.zip
```

Zip layout it produces (the structure recovery expects), signed whole-file (`-w`):

```
META-INF/com/google/android/update-binary   (the updater you supply)
META-INF/com/google/android/updater-script   (Edify: update_dynamic_partitions + raw write)
dynamic_partitions_op_list                    (resize system <image-size>)
system.img
```

Important caveat: this GSI build sets `target_recovery=false`, so it ships NO
Edify `updater` binary, and the stock recovery's native sideload path is A/B
`update_engine_sideload` (payload, which switches slots). So the Edify zip needs
an arm64 `updater` you supply (`--updater`): build it from a recovery-enabled
config (`m updater`) or take a compatible Lineage 21 arm64 one. Without it the
zip has no update-binary and recovery rejects it. This is why **fastbootd is the
recommended path** for a GSI; the recovery zip is provided for completeness and
needs an updater plus on-device testing.

## Flash ANY partition (generalized, self-contained)

`scripts/build_flash_ota.sh` builds a testkey-signed recovery zip that writes any
set of partitions on the current slot, no slot switch. It is self-contained: it
uses the vendored `prebuilt/update-binary-arm64` (the Edify updater), the vendored
`tools/signing/signapk/`, and `keys/testkey`.

It handles both partition classes automatically (or override with `:logical` /
`:physical`):
- logical (dynamic, in super: system, system_ext, product, vendor, odm,
  vendor_dlkm, odm_dlkm): resized to fit and written via
  `/dev/block/mapper/<name>`.
- physical (boot, vendor_boot, dtbo, vbmeta, recovery, abl, xbl, tz, aop,
  devcfg, ...): written via
  `/dev/block/bootdevice/by-name/<name><slot_suffix>`, the current slot resolved
  at flash time with `getprop ro.boot.slot_suffix`.

```
# system GSI only:
scripts/build_flash_ota.sh --out sys.zip \
  --part system:out/home/build-output/lineage-21.0-20260817-UNOFFICIAL-arm64_bvN.img

# boot + dtbo together (physical, current slot):
scripts/build_flash_ota.sh --out bootset.zip \
  --part boot:boot.img:physical --part dtbo:dtbo.img:physical

# then: adb reboot recovery ; adb sideload <zip>
```

The Edify `updater` is vendored at `prebuilt/update-binary-arm64` (a
statically-linked arm64 ELF, built from the tree with `scripts/build_updater.sh`,
lunch `lineage_arm64_bvN-ap2a-userdebug`, `m updater`), so the flash-zip build is
fully offline. End-to-end verified: it assembles the zip and signs it with the
testkey (whole-file signature present).

Capability note: this updater registers `map_partition`, `update_dynamic_partitions`,
`package_extract_file`, `block_image_update`, `mount`, `set_metadata`, `run_program`
and more, but NOT `getprop`. So:
- logical partitions use `map_partition("<name>")` to resolve the current-slot dm
  device (correct and slot-safe, no getprop needed).
- physical A/B partitions have the slot suffix baked at build time via `--slot`
  (default `_a`, the device's current slot per recon); set `--slot _b` for the
  other slot. For boot/dtbo/vbmeta/firmware, fastboot is usually the cleaner tool.

## The key

`keys/testkey.{pk8,x509.pem}` is the AOSP public testkey, identical to the cert
in the device's `otacerts.zip` (sha256 `A4:0D:A8:0A:59:D1:70:CA:...`). Signing is
done with `signapk -w` (whole-file OTA signature), which is what recovery's
`verify_file` checks. Fastbootd flashing does not use the key.

## Device finding: this recovery is A/B-payload-only

Tested on the unit (root recovery). The whole-file testkey signature verifies and
the `META-INF/com/android/metadata` is parsed, but the recovery install path then
rejects the package:

```
E:Unexpected ota package type, expects AB, actual BLOCK
Install from ADB completed with status 1.
```

So this device's recovery only accepts A/B `update_engine` payload OTAs; it will
not run a legacy Edify (BLOCK) package through `adb sideload`, no matter how it is
signed. A current-slot, no-slot-switch system flash therefore cannot go through
the recovery install path here. The working routes for a system-only, no-slot-
switch flash on this device are:
- fastbootd: `adb reboot fastboot ; fastboot flash system <gsi>.img` (canonical
  GSI flash, current slot, auto-resized, no slot switch). Recommended.
- root recovery bypass: with a root recovery shell (docs/13), run the vendored
  update-binary directly on the package (skips the recovery's AB-only check),
  which executes the Edify script (`update_dynamic_partitions` + `map_partition`
  write) on the current slot.

The A/B payload path (native to this recovery) writes the OTHER slot and switches
slots, which is not what we want.
