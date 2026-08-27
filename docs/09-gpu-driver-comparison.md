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

## Vulkan extension diff (quantified)

Extension identifiers present in each binary (string-level, a close proxy for the
advertised set): stock blob ~111, Turnip ~420. The blob-only set is just two
Qualcomm vendor extensions, irrelevant to portable apps:

```
VK_QCOM_profiling
VK_QCOM_render_pass_external_format
```

Everything else the blob exposes, Turnip also exposes. The gap runs the other
way: Turnip adds the entire modern feature set. The extensions that matter most
for DX-to-Vulkan translation (Winlator / DXVK / VKD3D-Proton) break down as:

| extension | blob 0615.91 | Turnip 26.1.1 |
|-----------|--------------|---------------|
| VK_KHR_swapchain | yes | yes |
| VK_EXT_robustness2 | yes | yes |
| VK_EXT_transform_feedback | yes | yes |
| VK_EXT_custom_border_color | yes | yes |
| VK_KHR_draw_indirect_count | yes | yes |
| VK_EXT_extended_dynamic_state | yes | yes |
| VK_EXT_extended_dynamic_state3 | **no** | yes |
| VK_KHR_dynamic_rendering | **no** | yes |
| VK_EXT_graphics_pipeline_library | **no** | yes |
| VK_EXT_shader_object | **no** | yes |
| VK_EXT_vertex_input_dynamic_state | **no** | yes |
| VK_EXT_buffer_device_address | **no** | yes |
| VK_EXT_4444_formats | **no** | yes |
| VK_KHR_maintenance5 (and 4/6/7/8/9) | **no** | yes |
| VK_EXT_descriptor_buffer | **no** | yes |
| VK_EXT_fragment_shader_interlock | **no** | yes |

The blob covers the older DXVK baseline but is missing the newer pillars that
current DXVK and VKD3D-Proton lean on: dynamic rendering, graphics pipeline
library / shader object (fast pipeline creation, less stutter), buffer device
address (required by many VKD3D-Proton paths and modern DXVK), extended dynamic
state 3, and the maintenance4-9 chain. This is the concrete, measurable reason
Turnip enables Windows-game and modern-console emulation on this handheld that
the 0615.91 blob cannot, and it is the strongest argument for the driver swap.

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

## Complete system-wide replacement (done, reproducible)

The Android Vulkan loader opens the driver by path
(`ro.hardware.vulkan=adreno` -> `/vendor/lib64/hw/vulkan.adreno.so`) and calls its
`HMI` hwvulkan module. Turnip built for Android exports `HMI` (verified with
`readelf`), needs only standard libs, and handles Gralloc4, so making Turnip that
file replaces the system Vulkan driver for every app. GLES/EGL stays Qualcomm
(`ro.hardware.egl=adreno`).

Two things must be handled or apps cannot load it:
- Size: Turnip (16.9 MB) is ~13 MB larger than the blob (4 MB) and the stock
  vendor ext4 has only ~2.7 MB free, so the image is grown first (resize2fs).
- SELinux: the stock driver is labelled `u:object_r:same_process_hal_file:s0`
  (the same-process-HAL context, it is dlopen'd into every app). The replacement
  must carry the same label and mode 0644.

`scripts/swap_vulkan_turnip.sh` does the offline image surgery and restores both:

```
scripts/swap_vulkan_turnip.sh <vendor_a.img> gpu/turnip-anbernic/vulkan.turnip.so vendor_turnip.img
```

Validated: the produced image passes `e2fsck`, and the embedded
`/vendor/lib64/hw/vulkan.adreno.so` is byte-identical to the Turnip binary with
the correct `same_process_hal_file` context. Flash it (bootloader unlocked;
fastbootd resizes the dynamic partition):

```
scripts/make_disabled_vbmeta.sh vbmeta.disabled.img
fastboot --disable-verity --disable-verification flash vbmeta vbmeta.disabled.img
fastboot reboot fastboot                 # enter fastbootd (dynamic partitions)
fastboot flash vendor vendor_turnip.img
fastboot reboot
```

On a userdebug + unlocked device the simpler route needs no reflash:

```
adb root && adb remount
adb shell cp /vendor/lib64/hw/vulkan.adreno.so /vendor/lib64/hw/vulkan.adreno.so.bak
adb push vulkan.turnip.so /vendor/lib64/hw/vulkan.adreno.so
adb shell restorecon /vendor/lib64/hw/vulkan.adreno.so && adb reboot
```

Compatibility caveat: the Anbernic Turnip declares `minApi 34` (Android 14), and
this device is Android 12 (vendor sdk 32). Turnip links only stable NDK libs and
detects gralloc at runtime, so it is expected to load, but this is below its
stated minimum and MUST be validated on device (check `adb shell dumpsys SurfaceFlinger | grep -i vulkan`, run a Vulkan app, watch `logcat` for loader/gralloc errors). Keep the `.bak` (or the stock `vulkan.adreno.so` committed in
`gpu/stock-qualcomm/`) as the revert. If HWUI is switched to Vulkan
(`ro.hwui.use_vulkan`), test the UI too; the blob is usually better for the
compositor.

## Is the Anbernic Turnip patched, or stock upstream?

Stock upstream, confirmed by building the exact same version (Mesa 26.1.1) from
upstream and diffing:

- Exported driver symbols: identical (Anbernic 234 vs upstream 235 FUNC symbols,
  and the only differences are libc imports `__stack_chk_fail` / `__assert2` /
  `__register_atfork`, not Turnip functions).
- driconf per-game profile database: identical (both 106 `.exe` app profiles, the
  same names `APlagueTaleRequiem_x64.exe`, `AtlasFallen (VK).exe`, `BatmanAK.exe`,
  ... which is Mesa's stock `drirc`, unchanged).
- Turnip source-file set: identical.
- No fork markers (no K11MCH1 / bylaws / kimchi / custom option or game-hack
  strings).

The observable differences are not code:
- Anbernic ships an unstripped debug build (6 `.debug` sections; a stock release
  build has 0). That accounts for the size (16.9 vs 16.0 MB) and the ~11k
  "unique" strings, which are all debug-symbol and shader-blob noise.
- The AdrenoTools packaging metadata declares `minApi 34` (Android 14).

So Anbernic simply took upstream Mesa 26.1.1, built it for their handheld (KGSL,
Android, debug info left in), and packaged it. There is no vendor secret sauce.
Consequence: our own build (Opportunity 2) at Mesa 26.3.0-devel, stripped, and
targeting Android 12 (API 31) is a newer, better-targeted equivalent, and any
real optimization has to come from build options / tuning, not from something
Anbernic did.

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

### Done: our own Turnip build

`scripts/build_turnip.sh` cross-builds it and `gpu/turnip-selfbuilt/` holds the
result. Details of what was done:

- Toolchain: Android NDK r27c clang 18, meson 1.4 / ninja, `glslangValidator`
  built from source (needed for the ASTC/BVH meta shaders).
- Cross file targets `aarch64-linux-android31` (**API 31 = Android 12**), which
  removes the Anbernic build's minApi-34-vs-Android-12 mismatch, and static-links
  libc++ so the driver depends only on standard system libs (no
  `libc++_shared.so`).
- Configured Vulkan-only on the KGSL backend:
  `-Dvulkan-drivers=freedreno -Dgallium-drivers= -Dfreedreno-kmds=kgsl
  -Dplatforms=android -Dandroid-stub=true -Degl=disabled -Dgles1/2=disabled
  -Dllvm=disabled`.
- One source fix was required: the ASTC decoder compute shader uses
  `local_size_x_id` (spec-constant workgroup size), which needs SPIR-V >= 1.2,
  but the stock meson rule invokes glslang with the SPIR-V 1.0 default. The
  script patches that rule to pass `--target-env spirv1.3`.

Result: `vulkan.turnip.so`, **Mesa 26.3.0-devel**, a702 device support, KGSL,
exports `HMI` (system-loadable), NEEDED = only `libhardware liblog libnativewindow
libsync libm libz libdl libc` (self-contained, same profile as the Anbernic
build). Verified with `readelf`/`strings`; on-device validation still required.

Deploy it exactly like the Anbernic driver: AdrenoTools per-app injection, or the
system-wide swap via `scripts/swap_vulkan_turnip.sh gpu/turnip-selfbuilt/vulkan.turnip.so`.

Tuning knobs to explore from here (rebuild + A/B): `TU_DEBUG` flags (`sysmem`,
`gmem`, `nolrz`, `flushall`, `noconform`), ir3 shader-compiler options, trimming
extensions to the target titles, and pinning a702-specific workarounds. This
composes with the pure-DTB GPU overclock (docs/04).

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
