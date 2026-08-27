# Adjustable levers, at a glance

Operator-facing summary of what can actually be changed on this device
(SM6450 Parrot / SM4375 Ravelin), ordered safest to hardest. Detail and evidence
are in docs/04 (research), docs/06 and docs/07 (CPU firmware RE).

## GPU: fully adjustable, pure DTB edit (the clean win)

The device tree is not in the secure-boot chain, so GPU edits need no firmware
re-signing.

| Lever | Where | Tool |
|-------|-------|------|
| Top GPU frequency | `vendor_boot` DTB, `qcom,gpu-pwrlevel@0`, `qcom,gpu-freq` | `scripts/gpu_overclock.sh` (raise top) |
| New top pwrlevel (keep stock default) | new `qcom,gpu-pwrlevel` + renumber | `tools/dtb/add_gpu_level.py` |
| Voltage corner per level | `qcom,level` (RPMh corner, TURBO = 0x1A0) | edit in DTS; cannot exceed TURBO |
| DDR bandwidth vote per level | `qcom,bus-freq-ddr7/ddr8` (index) | already at max index on the top level |

- Stock ceilings: Parrot/Adreno 710 = 940 MHz, Ravelin/Adreno 613 = 1010 MHz.
  Realistic OC ~1000-1050 / ~1050-1100 MHz.
- End-to-end: `scripts/flash_gpu_oc.sh <stock_vendor_boot.img> parrot 1000`
  (repack + verification-disabled vbmeta + flash). Needs the bootloader unlocked.
- Restore: `scripts/restore_stock.sh`.

## CPU: no static edit on this device, live LUT only

Traced through cpucp.elf (RISC-V), xbl_s.melf, devcfg.mbn, xbl_config.elf and the
decompressed uefi.elf ClockDxe. There is no frequency table in any shipped image
to patch; the operating-point plan is composed at runtime from the EPSS hardware
LUT (docs/06, docs/07).

| Lever | Where | Tool |
|-------|-------|------|
| Live CPU freq LUT | EPSS registers, domain0 0x17d91000 / domain1 0x17d92000 | `tools/fw/epss_lut.sh dump` / `write` |

- lval = target_freq / 19.2 MHz. Stock ~2.0 GHz efficiency, ~2.2 GHz prime.
- Writes are experimental, root-only, and must stay within the CPRh voltage
  envelope or the CPU hangs. Read first.

## DDR / memory: ceiling not adjustable from a plaintext table

- DTB `ddr-freq-table` is only a menu of operating points the DDR DCVS driver may
  vote for; it cannot exceed the trained ceiling. Stock: LPDDR4X 2092 MHz,
  LPDDR5 3196 MHz clock.
- The real ceiling is in the BCM vote vectors plus XBL DDR training (signed, in
  BCM units, not plain MHz). Raising it risks untrained-DDR no-boot. Not a clean
  lever.
- The aop.mbn tables near `ebi.mol` are NoC/LLCC bus clocks (352-680 MHz), not
  the DDR data clock (docs/04 section 3.4). Editable with a firmware re-sign if
  bus tuning is ever wanted, but that is not DDR.

## Firmware editing in general (ABL/XBL/devcfg/...)

- The whole chain is signed with Qualcomm public test keys, so re-signing is
  possible: `scripts/resign_firmware.sh` uses `qtestsign` (unfused, MBN v6) or the
  vendored `sectools` (fused). Needed for any bus/NoC or theoretical DDR firmware
  edit.
- Gate: confirm fuse state with `fastboot oem device-info` before touching XBL.
  A bad XBL is EDL-only (recover via `xbl_s_devprg_ns.melf`, docs/05).

## Bottom line

- Do now, low risk: GPU overclock (DTB only). The one production-quality lever.
- On-device experiment only: CPU via the live EPSS LUT.
- High risk / firmware re-sign: NoC/LLCC bus clocks. DDR is effectively off-limits
  without training work.
