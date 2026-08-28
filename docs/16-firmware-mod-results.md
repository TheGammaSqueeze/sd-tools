# RG 55G1 (RavelinP / SG4250P): what can be customized and boot

Summary of which firmware/partitions were modified (and where needed, re-signed
with the vendored SecTools **test keys** via `tools/signing/qtestsign`) and
actually booted on the device (serial a28c0e0e). The device is UNLOCKED with
**secure boot unfused** - the stock images are themselves SecTools test-key
signed, so test-key re-signing is accepted for most partitions.

## Customized + booted successfully (device-confirmed)

| Partition / image | What was changed | Signing | Boots |
|-------------------|------------------|---------|-------|
| **ABL** (`abl.elf`) | re-signed via qtestsign (`modified/firmware/abl.qtestsign.elf`) | qtestsign test-key MBN | yes |
| **boot.img** | kernel cmdline `enforcing=0 androidboot.selinux=permissive audit=0`; built from the LIVE `lun6_boot_a` dump via abie | unsigned AVB footer (unlocked bootloader) | yes (live) |
| **vendor_boot.img** | permissive cmdline + first-stage fstab **avb flags stripped** (all `avb`/`avb=vbmeta_system`/`avb_keys=`, keys kept) + **ramoops console zone** added to the DTB (`console-size 0x100000`, `record-size 0x20000`, `max-reason 5`); rebuilt with the **AOSP dtc** (never host dtc - it mangles `qcom,gpu-freq`) | unsigned AVB footer | yes (live: `console_size=1048576`, `/vendor_dlkm` mounts plain ext4 = no verity) |
| **vendor_dlkm** | ext4 repacked in place via `debugfs` (module swap, `security.selinux`/mode preserved); used to swap `gpucc-ravelin.ko` (in-place GPU-clock OC) | none needed (verity bypassed via the vendor_boot fstab strip) | yes |
| **recovery** | keyless root-adb prop patch (`ro.secure=0`/`ro.adb.secure=0`/`ro.debuggable=1`) | unsigned (docs/13) | yes |
| **vbmeta** | `--disable-verity --disable-verification` | n/a | yes |

Key enabler: because the vendor_boot first-stage fstab has AVB stripped and the
cmdline is permissive, a **modified vendor_dlkm mounts as plain ext4 and boots**
without re-signing - this is how the GPU-clock experiments were deployed. Always
flash via **fastbootd** (`adb reboot fastboot`); bootloader fastboot rejects
`vendor_boot` writes.

## Does NOT boot - hard bricks (do not attempt)

| Partition | What happened |
|-----------|---------------|
| **AOP** (`aop.mbn` -> `aop_a`) | Re-signing with qtestsign - even the **stock, unmodified** content - does NOT boot. The AOP is the always-on power controller and its XBL loader does not accept the qtestsign-restructured ELF (qtestsign relocates the hash segment; this is fine for ABL but not for AOP on this SoC). Result: hard brick, no adb/fastboot/EDL enumeration, recoverable only by **physically** entering EDL 9008 + QFIL-flashing stock `aop_a`. **Never qtestsign+flash the AOP here.** The stock factory `aop_a` is saved at `/work/55g1/aop/aop_a.bin`; recovery writeup at `/work/55g1/aop/BRICK_RECOVERY_README.md`. |

Consequence for GPU OC: the AOP was the only remaining lever to raise the GX
voltage above TURBO_L1 (the platform ARC power-table cap that limits the GPU to
1010 MHz - see the root-cause section of docs/14). Since the AOP cannot be
re-signed/flashed without bricking, that lever is closed, and **1010 MHz is a
hard platform limit** on this device.

## The re-sign toolchain

`tools/signing/qtestsign` produces test-key-signed MBNs for the many Qualcomm
firmware types (`abl`, `aop`, `tz`, `xbl`, `cpucp`, `shrm`, ...). It works on this
unfused device for ABL. `tools/signing/inspect_mbn.py` dumps the ELF segments and
embedded certs. The stock images already carry the "SecTools ... Test Key" chain,
confirming the device accepts test-key firmware - with the AOP being the one
proven exception.
