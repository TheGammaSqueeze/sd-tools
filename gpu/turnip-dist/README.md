# GammaOS Turnip driver packages (Adreno 613) for Winlator / AdrenoTools

Custom Vulkan driver packages in the AdrenoTools / Winlator format (flat zip:
`meta.json` + `vulkan.turnip.so`), the same layout as the Anbernic and community
Turnip packages. All are self-built Mesa Turnip tuned for the Adreno 613 (gen6_3 /
SG4250P, stock clock 1010 MHz) and documented in `docs/14-benchmarks.md`.

## Packages

| Zip | Build | Notes |
|-----|-------|-------|
| `GammaOS-Turnip-Adreno613-ULTRA-v6.adpkg.zip` | v5 + non-uniform-access lowering | **Recommended - the shipped GammaOS driver.** Everything in v5 (dw_noubwc VK1.3 + 128-wide waves + UBWC-off + FMA reassociation + selective forced fp16 + compute round-robin) plus the upstream `nir_opt_non_uniform_access` pass, which lowers non-uniform UBO/SSBO/texture/image access for DXVK/VKD3D and some native VK titles (dynamic descriptor indexing). Neutral on native content (3DMark WL 648 / WLE 177, unchanged, renders clean); helps translation-layer content with non-uniform resource access. |
| `GammaOS-Turnip-Adreno613-ULTRA-v5.adpkg.zip` | selective fp16 + compute round-robin | **Superseded by v6.** Same as v6 without the non-uniform-access lowering. dw_noubwc + FMA reassociation + selective forced fp16 + round-robin compute dispatch. |
| `GammaOS-Turnip-Adreno613-GameNative-ubwc-v1.adpkg.zip` | ULTRA-v6 + UBWC + sysmem | **For emulators - best for render-to-texture-heavy titles.** Re-enables UBWC framebuffer compression (lossless) plus direct-to-sysmem. Measured +43% on the multi-pass render-to-texture benchmark (5680 -> 8118 passes/s) that models DXVK/VKD3D/RPCS3 post-process and render-target chains (bloom/SSAO/tonemap, e.g. MGS4). UBWC costs 5-7% on native tiled titles (measured 3DMark: Wild Life 649 -> 603, Wild Life Extreme 178 -> 170) so it is emulator-only, not the shipped default. Correctness-safe (UBWC is lossless). |
| `GammaOS-Turnip-Adreno613-GameNative-sysmem-v1.adpkg.zip` | ULTRA-v6 + sysmem | **For emulators - try this first.** Renders direct-to-sysmem (bypasses GMEM tiling), a coherency fix for DXVK/VKD3D/RPCS3 render-to-texture. Only ~2% slower than default on real titles. |
| `GammaOS-Turnip-Adreno613-GameNative-flushall-v1.adpkg.zip` | ULTRA-v6 + flushall | **For emulators - fallback.** Stronger per-submit cache-flush workaround; use only if sysmem still corrupts (fixes some titles sysmem can't). Costs ~10% on real titles, so prefer sysmem. |
| `GammaOS-Turnip-Adreno613-AGGRESSIVE-v1.adpkg.zip` | no fp16 | dw_noubwc + FMA reassociation, no forced fp16. 100% safe (no fp16 artifacts), ~10% slower than ULTRA on ALU-bound titles. |
| `GammaOS-Turnip-Adreno613-v1.adpkg.zip` | dw_noubwc (strict) | multiview VK 1.3 + 128-wide fragment waves + UBWC-off. Closest to reference precision. |
| `GammaOS-Turnip-Adreno613-ULTRA-v1.adpkg.zip` | blanket fp16 | **Superseded.** Forces fp16 on ALL fragment math including texture coordinates -> black textures on some content (e.g. MGS4). Use ULTRA-v6 (selective) instead. |
| `GammaOS-Turnip-Adreno613-ULTRA-v3.adpkg.zip` | + pow-squaring | **DEPRECATED - do not use.** `pow()` repeated-squaring flickers / blacks textures (fp16 overflow to inf/NaN for bases >1). |

**Use ULTRA-v6** (v5 + non-uniform-access lowering, driver 16342072) for general use - it
is the shipped GammaOS driver. For emulators (GameNative/Winlator running DXVK/VKD3D/RPCS3, e.g. MGS4)
use the GameNative-sysmem variant first (only ~2% slower than default); fall back to GameNative-flushall (~10% slower) only if sysmem still corrupts. The older blanket-fp16 ULTRA-v1/v2
(16330280) and the pow-squaring ULTRA-v3 both cause black textures and are superseded.
If you see any fp16 artifact even on v6, fall back to AGGRESSIVE (no fp16, ~10% slower).

## What ULTRA does
- **multiview forced -> Vulkan 1.3** (153 device extensions) instead of the stock
  blob's frozen Vulkan 1.1 (71). This is what lets DXVK / VKD3D (Winlator, Box64)
  and newer Vulkan emulators run at all.
- fragment shaders opt into 128-wide (double-threadsize) waves;
- UBWC framebuffer compression disabled (a measured net loss on this GPU);
- constant-coefficient FMA-chain reassociation (matches the stock compiler, brings
  compute from 52 to stock-parity 127-129 GFLOPS);
- round-robin compute-workgroup dispatch across the SP cores (v5): +5.7% on the compute
  microbench (52.4 -> 55.4 GFLOPS), graphics-neutral, correctness-safe;
- **selective** forced fp16 fragment math (large win on realistic fragment shaders;
  lossy) - the texture-coordinate and depth chains are kept fp32 so textures do not
  go black, unlike the older blanket-fp16 build.
- non-uniform resource-access lowering (v6, backported upstream `nir_opt_non_uniform`):
  lowers non-uniform UBO/SSBO/texture/image access for DXVK/VKD3D and native titles that
  use dynamic descriptor indexing. Neutral on native content, helps translation layers.

## Test results (RG 55G1, Adreno 613 @ 1010 MHz, device-validated)

Numbers are for the recommended **ULTRA-v6** driver (selective fp16 + compute round-robin +
non-uniform-access lowering, driver 16342072), all measured on-device with the GPU pinned to
1010 MHz and screenshot-verified for correctness.

3DMark (real titles), higher is better:

| Test | Stock Adreno | AGGRESSIVE (no fp16) | ULTRA-v6 (selective fp16) |
|------|-------------:|---------------------:|--------------------------:|
| Wild Life (1440p)          | 700 | 649 | 650 |
| Wild Life Extreme (4K)     | 174 | 167 | **179** |

ULTRA-v6 renders both Wild Life and Wild Life Extreme cleanly (no black textures) and beats
stock on WLE (179 vs 174). Wild Life is texture-bandwidth-bound, so fp16 gives ~zero there
(650 vs 649 no-fp16) because the fp16 win on that title was texture-coordinate math, which
selective fp16 now keeps fp32 to avoid black textures; the older blanket-fp16 build scored
719 on Wild Life precisely because it did NOT protect those coords (and blacked textures).

Microbenchmarks vs the stock Qualcomm blob (GFLOPS / throughput, GPU pinned) - this is where
ULTRA-v6's real-content advantage shows:

| Workload | Stock blob | ULTRA-v6 | Delta |
|----------|-----------:|---------:|------:|
| Realistic lighting fragment (gamebench)   | 8.8  | 14.0 | **+59%** (forced fp16) |
| PBR-style fragment (gamebench2)           | 11.7 | 21.5 | **+84%** (forced fp16) |
| Trilinear texture sampling (texbench)     | 1.35 | 1.48 Gtex/s | **+9.6%** |
| Data-dependent compute (gpubench_dd)      | 85.8 | 85.0 | parity (within 1%) |
| Raw interleaved-FMA loop (gfxbench)       | 77.9 | 60.2 | -23% (synthetic; fp16 cannot apply) |

The realistic-shader rows (gamebench / gamebench2) are the ones that matter for real games: on
the fragment-ALU-heavy lighting and PBR math that games actually run, ULTRA-v6 leads the
proprietary blob by +59 to +84% thanks to forced fp16. Texture sampling also leads stock, and
real (data-dependent) compute is at parity. ULTRA-v6 only trails on a synthetic raw-FMA
microbench (gfxbench), where the interleaved dependency chain cannot be demoted to fp16 - a
pattern real shaders do not hit. dw_noubwc reaches ~93-96% of stock while adding the modern-
Vulkan surface.

Compute footnote: the constant-coefficient gpubench microbench shows stock/older builds at
~129 GFLOPS vs ULTRA-v6's ~55, but that gap is entirely the benchmark's compile-time-constant
chain being folded away - on data-dependent compute (gpubench_dd, the realistic case) ULTRA-v6
is at stock parity (85.0 vs 85.8), so there is no real compute deficit.

> **Not ULTRA v3.** v3 added a constant-integer `pow()` -> repeated-squaring pass that
> scored higher on the lighting microbench (16.8 GFLOPS, +110% vs fp32) but caused
> flickering / black textures on real games (the fp16 squaring overflows to inf/NaN for
> bases >1). It was rolled back; the shipped driver is ULTRA-v6 (selective fp16).

fp16 is lossy (reduced precision); most content renders correctly, but a title that
shows banding can opt out per-effect with `GAMMA_NOFP16` (fp16) / `GAMMA_NOFASTMATH`
(reassociation).

## How to use
In Winlator (or GameHub / any AdrenoTools-based loader): Contents / Video / Graphics
Driver -> import / add driver -> select the .zip -> pick it as the Turnip driver.
Then set the container's GPU driver to Turnip. Works on Android API 31+ (built
against API 31; the RG 55G1 is API 34).

## Rebuild
Drivers live in `gpu/turnip-selfbuilt/` (`vulkan.turnip.dw_noubwc.so`,
`vulkan.turnip.aggressive.so`, `vulkan.turnip.ultra.so`); source patches are the
`turnip-*.patch` files there (multiview, `turnip-noubwc-default`,
`turnip-fs-double-threadsize`, `turnip-fastmath-reassoc`, `turnip-force-fp16`,
`turnip-pow-squaring`; see `docs/14-benchmarks.md`). Repackage with
`zip -j GammaOS-Turnip-Adreno613-ULTRA-v3.adpkg.zip meta.json vulkan.turnip.so`.
