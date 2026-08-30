# GammaOS Turnip driver packages (Adreno 613) for Winlator / AdrenoTools

Custom Vulkan driver packages in the AdrenoTools / Winlator format (flat zip:
`meta.json` + `vulkan.turnip.so`), the same layout as the Anbernic and community
Turnip packages. All are self-built Mesa Turnip tuned for the Adreno 613 (gen6_3 /
SG4250P, stock clock 1010 MHz) and documented in `docs/14-benchmarks.md`.

## Packages

Latest at the top. Click a package name to download the zip.

| Zip (download) | Build | Notes |
|----------------|-------|-------|
| [GammaOS-Turnip-Adreno613-GameNative-ubwc-nofp16-v1.adpkg.zip](GammaOS-Turnip-Adreno613-GameNative-ubwc-nofp16-v1.adpkg.zip) | ubwc + selective-ubwc, no forced fp16 (v7) | **RECOMMENDED default for GameNative / Winlator emulation - import this one.** UBWC + direct-to-sysmem (the +43% multi-pass render-to-texture win, 5680 -> 8118 passes/s, plus coherency) with forced fragment fp16 OFF, so it renders EVERY tested title correctly - including Fox Engine (MGS V: Ground Zeroes), where forced fp16 blacks the materials. **v7 adds selective UBWC:** UBWC stays on render targets (keeping the render-to-texture win) but is turned off for sample-only textures, which sample 2.1x faster uncompressed on the a613 (texbench 0.70 -> 1.48 gtex/s) with rtbench fully preserved (7756 -> 7803 passes/s). UBWC is a lossless compression layout so this cannot change pixels - device-validated clean AND visually unchanged on both MGS V: Ground Zeroes and MGS4 (Guns of the Patriots). Import into the emulator's graphics-driver picker; do NOT flash as the system driver (the /vendor driver stays ULTRA-v6). |
| [GammaOS-Turnip-Adreno613-GameNative-ubwc-v1.adpkg.zip](GammaOS-Turnip-Adreno613-GameNative-ubwc-v1.adpkg.zip) | ubwc + forced fp16 | **Faster on fp16-TOLERANT, GPU-bound titles only.** Same UBWC + sysmem plus forced fragment fp16 (up to +75/+84% on realistic lighting/PBR fragment ALU). Device-validated clean and faster than the community A12-fix on MGS4. BUT forced fp16 BLACKS textures on Fox Engine (MGS V: Ground Zeroes) and similar - a broad fp16 value-precision loss in the per-pixel material/lighting math that no keep-set can fix without forfeiting the speedup (texcoord, no-fastmath, and transcendental-protection builds were all tested and all still black). Use only on titles where it renders clean; if you see black textures, use ubwc-nofp16 above. |
| [GammaOS-Turnip-Adreno613-GameNative-ubwc-cfp16-v1.adpkg.zip](GammaOS-Turnip-Adreno613-GameNative-ubwc-cfp16-v1.adpkg.zip) | ubwc + compute fp16 | **Emulator, compute-heavy titles (opt-in, title-dependent).** ubwc plus forced fp16 on compute shaders (measured +124% on the compute microbench). Device-validated RENDERS CLEAN on MGS4 with a small gain, but forced compute fp16 BLACK-SCREENS some content (e.g. 3DMark Wild Life Extreme), so it is per-title opt-in, not a default - try it on a compute-heavy title and fall back to plain ubwc if anything corrupts. |
| [GammaOS-Turnip-Adreno613-GameNative-ubwc-only-v1.adpkg.zip](GammaOS-Turnip-Adreno613-GameNative-ubwc-only-v1.adpkg.zip) | ubwc, sysmem off | **Emulator A/B variant.** ubwc with direct-to-sysmem dropped, so it keeps on-chip GMEM tiling. FPS-neutral and clean on MGS4 (that title does not need the sysmem coherency workaround); try it if a title is bandwidth-bound. Falls back in behaviour to plain ubwc for coherency-sensitive titles. |
| [GammaOS-Turnip-Adreno613-GameNative-sysmem-v1.adpkg.zip](GammaOS-Turnip-Adreno613-GameNative-sysmem-v1.adpkg.zip) | ULTRA-v6 + sysmem | **Emulator fallback.** Direct-to-sysmem coherency fix without UBWC. Try this if a specific title shows an artifact under the ubwc driver; ~2% slower than default on native, no UBWC. |
| [GammaOS-Turnip-Adreno613-GameNative-flushall-v1.adpkg.zip](GammaOS-Turnip-Adreno613-GameNative-flushall-v1.adpkg.zip) | ULTRA-v6 + flushall | **Emulator last-resort.** Stronger per-submit cache-flush (the same workaround the community A12-fix uses, but on newer Mesa + our compiler opts). Use only if both ubwc and sysmem still corrupt a title; costs ~10% on native. |
| [GammaOS-Turnip-Adreno613-GameNative-maxfp16-EXPERIMENTAL-v1.adpkg.zip](GammaOS-Turnip-Adreno613-GameNative-maxfp16-EXPERIMENTAL-v1.adpkg.zip) | blanket fp16 (frag+compute+vertex) | **Superseded by ubwc-cfp16.** Maximal forced fp16 everywhere; large ALU/compute win but blacks textures on many titles. Kept for reference; use GameNative-ubwc-cfp16 instead for the selective, safer compute-fp16 build. |
| [GammaOS-Turnip-Adreno613-ULTRA-v6.adpkg.zip](GammaOS-Turnip-Adreno613-ULTRA-v6.adpkg.zip) | v5 + non-uniform-access lowering | **RECOMMENDED system/`/vendor` driver (native Android).** Everything in v5 (dw_noubwc VK1.3 + 128-wide waves + UBWC-off + FMA reassociation + selective forced fp16 + compute round-robin) plus the upstream `nir_opt_non_uniform_access` pass for DXVK/VKD3D dynamic descriptor indexing. Neutral on native content (3DMark WL 648 / WLE 177, renders clean). This is the shipped GammaOS default; keep it flashed. |
| [GammaOS-Turnip-Adreno613-ULTRA-v5.adpkg.zip](GammaOS-Turnip-Adreno613-ULTRA-v5.adpkg.zip) | selective fp16 + compute round-robin | **Superseded by v6.** Same as v6 without the non-uniform-access lowering. |
| [GammaOS-Turnip-Adreno613-ULTRA-v4.adpkg.zip](GammaOS-Turnip-Adreno613-ULTRA-v4.adpkg.zip) | selective fp16 | **Superseded by v6.** Selective fp16 without compute round-robin or non-uniform lowering. |
| [GammaOS-Turnip-Adreno613-AGGRESSIVE-v1.adpkg.zip](GammaOS-Turnip-Adreno613-AGGRESSIVE-v1.adpkg.zip) | no fp16 | dw_noubwc + FMA reassociation, no forced fp16. 100% safe (no fp16 artifacts), ~10% slower than ULTRA on ALU-bound titles. Use if any fp16 build shows banding/artifacts. |
| [GammaOS-Turnip-Adreno613-v1.adpkg.zip](GammaOS-Turnip-Adreno613-v1.adpkg.zip) | dw_noubwc (strict) | multiview VK 1.3 + 128-wide fragment waves + UBWC-off. Closest to reference precision. |
| [GammaOS-Turnip-Adreno613-ULTRA-v3.adpkg.zip](GammaOS-Turnip-Adreno613-ULTRA-v3.adpkg.zip) | + pow-squaring | **DEPRECATED - do not use.** `pow()` repeated-squaring flickers / blacks textures (fp16 overflow to inf/NaN for bases >1). |
| [GammaOS-Turnip-Adreno613-ULTRA-v2.adpkg.zip](GammaOS-Turnip-Adreno613-ULTRA-v2.adpkg.zip) | blanket fp16 | **Superseded.** Blanket fp16 on all fragment math incl. texture coords -> black textures on some content. Use ULTRA-v6 (selective). |
| [GammaOS-Turnip-Adreno613-ULTRA-v1.adpkg.zip](GammaOS-Turnip-Adreno613-ULTRA-v1.adpkg.zip) | blanket fp16 | **Superseded.** Same blanket-fp16 black-texture issue as v2. Use ULTRA-v6 (selective) instead. |

There are two roles here, do not mix them up:

- **System driver (flashed to `/vendor`): ULTRA-v6** (driver 16342072). This is what native
  Android games/apps and the UI use. It keeps UBWC off and GMEM tiling on for the best native
  speed and battery. This is the shipped GammaOS default and should stay flashed.
- **Emulator driver (imported into GameNative / Winlator): GameNative-ubwc-nofp16.** GameNative and
  Winlator load their OWN driver via AdrenoTools and ignore the system driver, so import a GameNative
  driver into the emulator's graphics-driver picker to get the UBWC render-to-texture win. **ubwc-nofp16
  is the recommended default** - it renders every tested title correctly (MGS4 and MGS V: Ground
  Zeroes) and keeps UBWC + sysmem. Use the fp16 ubwc build only on titles that tolerate forced fp16
  and are GPU-bound (extra fragment speed), and switch back to ubwc-nofp16 the moment a title shows
  black textures - forced fp16 blacks Fox Engine materials and cannot be made safe there (tested).
  Fall back to GameNative-sysmem, then GameNative-flushall, only if a title shows a coherency artifact.

Import note: GameNative parses driver `meta.json` with a comma-splitting key-value parser, so the
`name`/`description` must be short and comma-free and the library must be named
`libvulkan_freedreno.so` - the shipped GameNative-* zips are packaged that way (a comma in the meta
crashes GameNative's driver dialog on import).

The older blanket-fp16 ULTRA-v1/v2 (16330280) and the pow-squaring ULTRA-v3 both cause black
textures and are superseded. If you see any fp16 artifact even on v6, fall back to AGGRESSIVE
(no fp16, ~10% slower).

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
