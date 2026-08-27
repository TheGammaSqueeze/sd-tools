# Device and package inventory

Source package: `/mnt/c/55g1/V3.0_debug_20260810` (Qualcomm QFIL/QDL layout,
`rawprogram*.xml` + `patch*.xml`). Total ~3.7 GB (super/userdata not vendored).

## SoCs bundled in vendor_boot (15 device trees)

Selected at boot by `qcom,msm-id`:

| dtb index | model                         | family   | msm-id (soc_id) |
|-----------|-------------------------------|----------|-----------------|
| 00-03     | Montague / MontagueP (+4Gb)   | Montague | 0x245 (581)     |
| 04-08     | Parrot / ParrotP (+SG/+4Gb)   | Parrot   | 0x219 (537), 0x297, 0x265 |
| 09-14     | Ravelin / RavelinP (+SG/+4Gb) | Ravelin  | 0x238 (568)     |

- Parrot = SM6450, Snapdragon 6 Gen 1, GPU Adreno 710 (gen7-3-0).
- Ravelin = SM4375, Snapdragon 4 Gen 2, GPU Adreno 613.
- Montague = Adreno 613 class.

Confirm the physical unit on device:
```
getprop ro.board.platform
cat /sys/class/kgsl/kgsl-3d0/gpu_model
cat /proc/cpuinfo | grep -i "part\|implementer"
```

## Firmware signing state

Every boot-chain image is SecTools test-key signed except `multi_image_qti.mbn`
(genuine QTI root). Full table produced by `tools/signing/inspect_mbn.py`; see
`docs/01-secure-boot-and-signing.md`. Implication: secure boot fuse is very
likely open.

## Stock artifacts committed here

- `stock/firmware/` - abl.elf, xbl_s.melf, xbl_config.elf, xbl_s_devprg_ns.melf,
  devcfg.mbn, tz.mbn, aop.mbn, hypvm.mbn, cpucp.elf, uefi.elf, multi_image*.mbn.
- `stock/dtb/` - the split stock device trees (00.dtb .. 14.dtb), the joined
  `vendor_boot.dtb-section`, and reference decompiles `06.parrot.dts` /
  `11.ravelin.dts`.
- `stock/certs/` - the device's extracted signing chain (leaf/CA/root DER).

## Modifiable levers (summary, detail in docs/04)

| Target | Where | Editable without re-sign? |
|--------|-------|---------------------------|
| GPU freq/voltage | vendor_boot DTB `qcom,kgsl-3d0` pwrlevels | Yes (DTB only) |
| CPU freq/voltage | EPSS LUT from `devcfg.mbn` + `cpucp.elf` | No (firmware re-sign) |
| DDR/memory | trained by `xbl_config.elf`, voted by `aop.mbn`; DTB `ddr-freq-table` only exposes setpoints | No for the ceiling (firmware) |
