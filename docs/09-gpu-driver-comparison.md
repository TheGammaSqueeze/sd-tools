# GPU driver investigation: stock Qualcomm vs Mesa Turnip (Parrot / Adreno 710)

Compares the graphics driver shipped in this device's `super` image against the
Anbernic-built Mesa Turnip driver, and assesses whether swapping drivers or
building an optimized one is worthwhile.

Artifacts in `gpu/`:
- `gpu/stock-qualcomm/vulkan.adreno.so` - extracted from `vendor_a.img`
  (`/vendor/lib64/hw/vulkan.adreno.so`), plus `libadreno_utils.so`.
- `gpu/turnip-anbernic/vulkan.turnip.so` + `meta.json` - the attached Turnip.

## How the stock driver was extracted

The `super` partition ships as raw chunks `super_1..7.img` placed at 4096-byte
sector offsets given in `rawprogram*.xml` (base sector 25640), with zero-fill
gaps (not sparse). Reassembled to `super.raw` (2.97 GB) by `dd`-ing each chunk at
`(start_sector - 25640) * 4096`, then `lpunpack super.raw` to get the logical
partitions. `vendor_a.img` is ext4; files pulled with `debugfs -R dump`.

Vendor confirmed as this device: `ro.product.vendor.name=parrot`,
`ro.board.platform=parrot`, fingerprint `qti/parrot/parrot:12/.../userdebug/test-keys`,
`ro.hardware.vulkan=adreno`, `ro.hardware.egl=adreno`.

## The GPU

- DTB: `qcom,adreno-gpu-gen7-3-0`, `qcom,gpu-model = "Adreno710v1"`, `gen7-gmu`.
- `libgsl.so` enumerates chip ids A605/A608/A620/A640/A650/A660/A680/**A702**.
  The Parrot "Adreno 710" is internal id **a702** (a gen7 low-tier part).
- Turnip carries a device record for **a702** (and a725), so it natively
  recognizes this exact silicon; its templated codegen instantiates `chip6/7/8`
  (a6xx / a7xx / a7xx-gen) paths.

Both drivers talk to the same kernel via **KGSL** (`/dev/kgsl-3d0`) - Turnip uses
`tu_knl_kgsl.cc`, not the msm DRM path. So Turnip is a userspace-only swap; no
kernel change is needed.

## Side-by-side

| | Stock Qualcomm | Mesa Turnip (Anbernic) |
|---|---|---|
| File / soname | `vulkan.adreno.so` / `vulkan.adreno.so` | `vulkan.turnip.so` / `libvulkan_freedreno.so` |
| Version | Adreno driver **0615.91**, branch `LA.VENDOR.1.0.11.00.00.770.073` | **Mesa 26.1.1**, Anbernic G1 GEN2 pkg v17 |
| Vulkan level | reports Vulkan HAL for Adreno (1.1-class blob, Android 12 vendor) | **Vulkan 1.4** (meta `driverVersion`), minApi 34 |
| Source | closed, proprietary | open (MIT), `src/freedreno/vulkan/*` |
| Size | 4.04 MB | 16.9 MB (unstripped, with debug_info) |
| GLES/EGL | yes, separate blobs (`libGLESv2_adreno.so` 5.7 MB, `libEGL_adreno.so`, `libGLESv1_CM_adreno.so`) | none, Vulkan-only |
| VK_ extension strings | ~111 | ~455 referenced |
| NEEDED libs | 21, incl. `libgsl`, `libadreno_utils`, `libllvm-glnext`, and the QTI display-mapper HAL chain (`vendor.qti.hardware.display.mapper@2.0/3.0/4.0`, `graphics.mapper@2/3/4`, `libhidlbase`) | 9, all standard: `libcutils libhardware liblog libnativewindow libsync libm libz libdl libc` |

The dependency contrast is the crucial part. The Qualcomm driver is welded into
the vendor stack (gsl kernel-abstraction lib, the Qualcomm LLVM shader compiler,
and the gralloc/display-mapper HALs for UBWC and HDR buffer handling). Turnip
pulls only base Android libs, which is exactly why it can be loaded as a
self-contained `.so` at runtime.

## Opportunity 1: use Turnip as a drop-in (viable, low risk)

Two mechanisms, both real on this device:

1. **Per-app injection via AdrenoTools (recommended).** `libadrenotools` lets an
   app `dlopen` a custom `vulkan.*.so` in place of the system Vulkan driver,
   with no root and no partition change. This is precisely the packaging of the
   attached file (`meta.json` schemaVersion 1 + `libraryName`), the format
   Winlator / mupen / Vita3K / GameHub / Dolphin-style front-ends consume. The
   Anbernic package is already targeted at the G1 Gen 2 (this Parrot handheld),
   so it is expected to load and run.
2. **System-wide Vulkan replacement.** Swap `/vendor/lib64/hw/vulkan.adreno.so`
   (or set a `ro.hardware.vulkan` alias) for Turnip. Feasible because Turnip's
   deps are all present, but note: it replaces ONLY Vulkan. GLES/EGL stays on the
   Qualcomm blobs (`ro.hardware.egl=adreno`), and Android UI (HWUI) can be told
   to use Vulkan via `ro.hwui.use_vulkan` - test carefully, the proprietary blob
   is usually better for UI/compositor and UBWC paths. Requires re-signing/repack
   of `vendor` or an overlay, and a verification-disabled vbmeta (see docs/05).

When Turnip tends to win on this class of device: modern Vulkan titles and
emulators (DXVK/VKD3D translation, Vulkan-native cores) where the proprietary
0615.91 blob is dated and Turnip 26.1.1 brings current extension coverage, bug
fixes and per-title workarounds. When the blob wins: native GLES apps, UI
compositing, UBWC/AFBC-heavy and HDR paths, and raw driver overhead on
already-fast titles.

## Opportunity 2: build our own optimized Turnip (viable, high value)

Turnip is upstream Mesa, so we can build and tune it for a702/gen7 ourselves:

- **Build:** cross-compile Mesa for `android-aarch64` with
  `-Dvulkan-drivers=freedreno -Dfreedreno-kmds=kgsl -Dplatforms=android`, package
  the resulting `libvulkan_freedreno.so` as `vulkan.turnip.so` with a `meta.json`
  for AdrenoTools. The KGSL kmd is the right backend for this stock kernel.
- **Tuning levers:** `TU_DEBUG` / `FD_MESA_DEBUG` flags (e.g. `sysmem` vs
  `gmem`/tiled, `nolrz`, `flushall`, `noconform`), the ir3 shader-compiler options,
  and per-app driver overrides. The unstripped Anbernic build even keeps
  `debug_info`, so it is straightforward to profile and A/B specific knobs.
- **Device-specific wins:** trim extensions the target titles do not use, pin
  known-good workarounds for a702, and match the GMEM/tile config to the Parrot's
  actual on-chip memory. Because the GPU overclock in this repo is a pure DTB edit
  (docs/04), a custom Turnip + a raised GPU pwrlevel can be validated together.
- **Cost:** Turnip on a702 is a first-class Mesa target, so this is a normal Mesa
  build, not a port. The main effort is packaging + per-title validation.

## Caveats and honest limits

- Turnip is Vulkan-only. It does not replace GLES/EGL/CL; those stay Qualcomm.
- KGSL-path Turnip depends on the stock kernel's KGSL ioctl surface; a very old
  or unusual KGSL can expose gaps. This Parrot kernel is a standard KGSL target.
- Some titles regress on Turnip vs the blob (driver-specific bugs, missing UBWC).
  Always keep the stock `vulkan.adreno.so` (committed here) to revert.
- The proprietary blob integrates the QTI display mapper for UBWC/HDR buffers;
  Turnip handles UBWC itself but the composition path differs.

## Bottom line

Swapping to Turnip is genuinely viable on this device and is the intended use of
the attached package (AdrenoTools per-app injection, no flashing). Building our
own optimized Turnip for a702/gen7 is well worth it: it is a standard Mesa build
(a702 is natively supported), it unlocks Vulkan 1.4 plus current fixes over the
dated 0615.91 blob, and it composes with the repo's pure-DTB GPU overclock for a
combined driver-plus-clock tuning path. Keep the proprietary blob for GLES, UI,
and as the revert target.
