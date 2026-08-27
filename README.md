# sd-tools

Tooling and research for inspecting, modifying, re-signing and repacking the
firmware of a Qualcomm Snapdragon device (flash package `55g1 / V3.0_debug`).
The package bundles three SoCs selected at boot by `qcom,msm-id`:

| Family   | SoC    | Marketing            | GPU        |
|----------|--------|----------------------|------------|
| Parrot   | SM6450 | Snapdragon 6 Gen 1   | Adreno 710 |
| Montague | SM7315-class | Snapdragon 4 Gen x | Adreno 613 |
| Ravelin  | SM4375 | Snapdragon 4 Gen 2   | Adreno 613 |

The physical unit is exactly one of these. **Confirmed by on-device recon
(docs/10): the unit is the Anbernic RG 55G1 = RavelinP (`soc_id 654`,
`SG4250P`/`SG_RAVELINP`), Adreno A12/613, Android 14, bootloader unlocked.** So
the Ravelin tables apply; the Parrot/Adreno 710 analysis is for a different SoC in
the package. `ro.board.platform=parrot` is only the platform family name.

## What is established

- The whole boot chain (XBL, ABL, TZ, AOP, devcfg, hyp, cpucp, ...) is signed
  with Qualcomm **SecTools test keys** ("General Use Test Key (for testing
  only)"), not production OEM keys. See `docs/01-secure-boot-and-signing.md`.
  This strongly implies secure boot is not fused, so re-signed images are
  accepted. Verify fuse state before modifying XBL.
- The GPU overclock is a pure device-tree edit (the DTB is not in the signed
  secure-boot chain here). CPU and DDR ceilings live in signed firmware.
  See `docs/04-overclocking-research.md`.
- Qualcomm DTBs must be round-tripped with the **AOSP dtc**, not the distro
  dtc. The distro dtc mangles integer properties such as `qcom,gpu-freq` into
  escaped strings (e.g. `"8\aC"`) and a text edit then corrupts the tree. See
  `docs/02-dtb-workflow.md`.

## Documentation

- [docs/01-secure-boot-and-signing.md](docs/01-secure-boot-and-signing.md) - the boot chain of trust, the test-key finding, fuse-state check, and both re-sign paths (qtestsign unfused, sectools fused).
- [docs/02-dtb-workflow.md](docs/02-dtb-workflow.md) - why the AOSP dtc, the appended-FDT container, round-trip fidelity, add/remove-node editing, the abie repack path.
- [docs/03-device-inventory.md](docs/03-device-inventory.md) - the 15 device trees, per-SoC msm-id, firmware signing table, committed stock artifacts.
- [docs/04-overclocking-research.md](docs/04-overclocking-research.md) - the deep GPU/CPU/DDR research: full pwrlevel enumerations, voltage corners, and where each ceiling lives.
- [docs/05-flashing-and-recovery.md](docs/05-flashing-and-recovery.md) - A/B partition map, fastboot and EDL flashing, vbmeta handling, one-shot orchestration, recovery kit.
- [docs/06-cpucp-riscv-lut.md](docs/06-cpucp-riscv-lut.md) - RISC-V disassembly of cpucp.elf proving the CPU LUT is not there.
- [docs/07-xbl-epss-lut.md](docs/07-xbl-epss-lut.md) - ARM64/UEFI analysis: no static EPSS LUT in the images, ClockDxe attribution, the live-LUT route.
- [docs/08-adjustable-levers.md](docs/08-adjustable-levers.md) - operator-facing summary of every adjustable lever, safest to hardest.
- [docs/09-gpu-driver-comparison.md](docs/09-gpu-driver-comparison.md) - stock Qualcomm `vulkan.adreno.so` (v0615.91) vs Mesa Turnip 26.1.1: extraction, side-by-side, and the drop-in / build-our-own opportunity.
- [docs/10-ondevice-recon.md](docs/10-ondevice-recon.md) - live adb recon: the unit is RavelinP (RG 55G1), Android 14, unlocked; real CPU/GPU frequencies; corrections to the Parrot assumption.
- [docs/11-refresh-flicker.md](docs/11-refresh-flicker.md) - refresh-rate-switch flicker: the non-seamless mode-group cause, a diagnostic script, and fixes (lock rate, group-switch policy, panel dtb VFP dfps).
- [PROGRESS.md](PROGRESS.md) - running ledger of done vs open work.

## Layout

```
prebuilt/         dtc-aosp-x86_64  (the DTB round-trip compiler, prebuilt)
tools/dtb/        split_dtb.py, join_dtb.py, verify_roundtrip.sh
tools/signing/    inspect_mbn.py, testkeys-secp384r1/, mrc_presigned_certs-secp384r1/,
                  qtestsign/ (stub signer for unfused parts)
patches/          abie-use-aosp-dtc.patch  (make Android_boot_image_editor use AOSP dtc)
stock/firmware/   stock XBL/ABL/TZ/... ELF+MBN as shipped
stock/dtb/        stock device trees (split) + reference decompiles
stock/certs/      the device's own extracted signing chain (leaf/CA/root)
tools/fw/         firmware RE tools (scan_freq_tables, cpucp/xbl disasm, extract_uefi, epss_lut)
third_party/abie  the PATCHED Android_boot_image_editor (source, vendored)
third_party/sectools  genuine QTI sectools + secp384r1 test keys (vendored)
modified/         modified images produced by the tools
docs/             the writeups
scripts/          setup.sh (builds the vendored abie), selftest.sh, overclock + flash scripts
```

## Quick start

```
scripts/setup.sh                                   # build the vendored abie (nothing is fetched)
tools/dtb/verify_roundtrip.sh stock/dtb/vendor_boot.dtb-section   # prove DTB round-trip
tools/signing/inspect_mbn.py stock/firmware/abl.elf              # read signing identity
scripts/selftest.sh                                             # regression-test the toolchain
```

## Overclock workflows

This unit is RavelinP (docs/10), so target the Ravelin trees (stock top 1010 MHz):

```
tools/dtb/add_gpu_level.py <in.dts> 1080 <out.dts> --corner=TURBO_L1              # add a new top level
scripts/repack_vendor_boot.sh <vendor_boot.img> ravelin 1080 <out.img>           # end-to-end repack
scripts/flash_gpu_oc.sh <vendor_boot.img> ravelin 1080 --addlevel                # repack + vbmeta + flash
scripts/resign_firmware.sh abl modified/firmware/abl.elf modified/firmware/abl.signed.elf   # re-sign (unfused)
```
(The Parrot examples elsewhere are for the other SoC in the package, not this unit.)

Everything is vendored in this repo; nothing is fetched from the network:

```
prebuilt/dtc-aosp-x86_64   AOSP dtc (prebuilt)
third_party/abie           the PATCHED Android_boot_image_editor (source, builds with its gradlew)
third_party/sectools       genuine QTI sectools + secp384r1 test keys
tools/signing/qtestsign    stub MBN signer for unfused parts
tools/signing/testkeys-secp384r1, stock/certs   the certs
```

`scripts/setup.sh` only builds the vendored abie (and rebuilds the dtc binary
only if the prebuilt is missing). Regenerable artifacts (the abie build output,
the decompressed UEFI tree, the 100MB repacked images) are gitignored.
