# sd-tools

Tooling and research for inspecting, modifying, re-signing and repacking the
firmware of a Qualcomm Snapdragon device (flash package `55g1 / V3.0_debug`).
The package bundles three SoCs selected at boot by `qcom,msm-id`:

| Family   | SoC    | Marketing            | GPU        |
|----------|--------|----------------------|------------|
| Parrot   | SM6450 | Snapdragon 6 Gen 1   | Adreno 710 |
| Montague | SM7315-class | Snapdragon 4 Gen x | Adreno 613 |
| Ravelin  | SM4375 | Snapdragon 4 Gen 2   | Adreno 613 |

The physical unit is exactly one of these. Confirm on device with
`getprop ro.board.platform` and `cat /sys/class/kgsl/kgsl-3d0/gpu_model`.

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
modified/         modified images produced by the tools
docs/             the writeups
scripts/          setup.sh (fetch/build external tools)
```

## Quick start

```
scripts/setup.sh                                   # build AOSP dtc, clone abie + sectools
tools/dtb/verify_roundtrip.sh stock/dtb/vendor_boot.dtb-section   # prove DTB round-trip
tools/signing/inspect_mbn.py stock/firmware/abl.elf              # read signing identity
```

External heavy tools (sectools ~270MB, the boot image editor toolchain) are
fetched by `scripts/setup.sh` into `external/`. The load-bearing small pieces
(AOSP dtc, the secp384r1 test keys and certs, qtestsign) are committed so the
repo is self-contained for the common workflows.
