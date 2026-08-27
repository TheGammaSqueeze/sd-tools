# Flashing and recovery

## Partition layout (measured from rawprogram*.xml)

The device is A/B slotted. Every boot-chain image has an `_a` and `_b` copy:

| image            | partitions                | source file            |
|------------------|---------------------------|------------------------|
| XBL              | `xbl_a` / `xbl_b`         | xbl_s.melf             |
| XBL config       | `xbl_config_a` / `_b`     | xbl_config.elf         |
| ABL              | `abl_a` / `abl_b`        | abl.elf                |
| AOP              | `aop_a` / `aop_b`        | aop.mbn                |
| CPUCP            | `cpucp_a` / `cpucp_b`    | cpucp.elf              |
| DEVCFG           | `devcfg_a` / `devcfg_b`  | devcfg.mbn             |
| HYP              | `hypvm` ...              | hypvm.mbn              |
| multi-image QTI  | `multiimgqti_a` / `_b`   | multi_image_qti.mbn    |
| multi-image OEM  | `multiimgoem_a` / `_b`   | multi_image.mbn        |
| vendor_boot      | `vendor_boot_a` / `_b`   | vendor_boot.img        |

Flash the slot the device is currently booting (`getprop ro.boot.slot_suffix`),
or flash both to be safe. The GPU overclock only touches `vendor_boot`; the CPU
and DDR overclock touch `devcfg` (and possibly `cpucp`).

## Before touching XBL: confirm the fuse state

See `docs/01`. If secure boot is fused you cannot boot a modified XBL and a bad
one is EDL-only. On this device the whole chain is test-key signed, which is
strong evidence the fuse is open, but confirm with `fastboot oem device-info`
before flashing XBL or devcfg.

## Path 1: fastboot (bootloader), the normal case

For the GPU overclock (DTB only, no re-sign):

```
scripts/repack_vendor_boot.sh <stock_vendor_boot.img> parrot 1000 out.img
fastboot flash vendor_boot_a out.img
fastboot flash vendor_boot_b out.img     # or just the active slot
fastboot reboot
```

For a firmware overclock (CPU/DDR), re-sign first (see docs/01), then:

```
scripts/resign_firmware.sh devcfg modified/firmware/devcfg.mbn modified/firmware/devcfg.signed.mbn
fastboot flash devcfg_a modified/firmware/devcfg.signed.mbn
fastboot flash devcfg_b modified/firmware/devcfg.signed.mbn
```

Note on vbmeta: the top-level `vbmeta.img` is signed (SHA256_RSA4096, flags=0)
and hashes vendor_boot, so a repacked vendor_boot is rejected unless AVB is
disabled. The OEM key is not available, so on an unlocked bootloader flash a
verification-disabled vbmeta:

```
fastboot flashing unlock                                  # if not already unlocked
scripts/make_disabled_vbmeta.sh modified/firmware/vbmeta.disabled.img
fastboot --disable-verity --disable-verification flash vbmeta modified/firmware/vbmeta.disabled.img
fastboot flash vendor_boot_a out.img
fastboot reboot
```

A locked bootloader ignores the disable flag; unlock first.

## One-shot orchestration

`scripts/flash_gpu_oc.sh` does the whole GPU path in one call: repack
vendor_boot with the chosen frequency, verify the edit is present and all 15
trees are valid FDTs, build the verification-disabled vbmeta, and flash. It is
DRY-RUN by default (prints the fastboot commands); add `--execute` to flash.

```
scripts/flash_gpu_oc.sh <stock_vendor_boot.img> parrot 1000            # dry run
scripts/flash_gpu_oc.sh <stock_vendor_boot.img> parrot 1000 --addlevel # add a level
scripts/flash_gpu_oc.sh <stock_vendor_boot.img> parrot 1000 --execute  # flash
```

Validated end-to-end on this package (dry run): repack applies the edit to all
five Parrot trees, all 15 trees re-extract valid, vbmeta built.

`scripts/restore_stock.sh <stock_vendor_boot.img> [stock_vbmeta.img]` prints (or
`--execute` runs) the commands to flash every stock boot-chain image back to
both slots from `stock/firmware/`.

## Path 2: EDL 9008 (firehose), for recovery or a bricked bootloader

The EDL Firehose programmer for this SoC is `xbl_s_devprg_ns.melf` (committed in
`stock/firmware/`, and referenced by the package's `rawprogram*.xml` /
`patch*.xml`). Force the device into EDL 9008 (usually a test-point or the
`fastboot oem edl` / `adb reboot edl` route), then either:

- QFIL (Qualcomm): load `xbl_s_devprg_ns.melf` as the programmer, add the
  `rawprogram*.xml` and `patch*.xml`, flash.
- edl (open source, bkerler, github.com/bkerler/edl):
  ```
  edl --loader=stock/firmware/xbl_s_devprg_ns.melf w abl_a modified/firmware/abl.signed.elf
  edl --loader=stock/firmware/xbl_s_devprg_ns.melf w vendor_boot_a out.img
  ```

Because the fuse is (very likely) open, even a bad XBL is recoverable this way:
the PBL still accepts the test-signed `xbl_s_devprg_ns.melf` loader. If the fuse
were blown, only the stock signed loader would load and you would be limited to
re-flashing stock images.

## Recovery kit

Keep these from `stock/firmware/` handy before any firmware flash:
- `xbl_s.melf`, `abl.elf`, `devcfg.mbn`, `cpucp.elf`, `aop.mbn`, `xbl_config.elf`
  (stock images to restore a slot),
- `xbl_s_devprg_ns.melf` (the EDL programmer),
- the package `rawprogram*.xml` / `patch*.xml` (partition map for QFIL/edl).

Restore a slot by flashing the stock image back to the same `_a`/`_b` label.
