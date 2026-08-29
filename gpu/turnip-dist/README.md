# GammaOS Turnip driver packages (Adreno 613) for Winlator / AdrenoTools

Custom Vulkan driver packages in the AdrenoTools / Winlator format (flat zip:
`meta.json` + `vulkan.turnip.so`), the same layout as the Anbernic and community
Turnip packages. All are self-built Mesa Turnip tuned for the Adreno 613 (gen6_3 /
SG4250P, stock clock 1010 MHz) and documented in `docs/14-benchmarks.md`.

## Packages

| Zip | Build | Notes |
|-----|-------|-------|
| `GammaOS-Turnip-Adreno613-v1.adpkg.zip` | dw_noubwc (strict) | multiview VK 1.3 + 128-wide fragment waves + UBWC-off. Closest to reference precision. |
| `GammaOS-Turnip-Adreno613-AGGRESSIVE-v1.adpkg.zip` | + constant-FMA reassociation | dw_noubwc plus stock-style FMA-chain reassociation (compute parity with stock). |
| `GammaOS-Turnip-Adreno613-ULTRA-v1.adpkg.zip` | + forced fp16 | **Recommended.** Everything above plus forced fp16 fragment math. Fastest that renders correctly; fp16 is lossy. |
| `GammaOS-Turnip-Adreno613-ULTRA-v3.adpkg.zip` | + pow-squaring | **DEPRECATED - do not use.** Adds constant-integer `pow()` -> repeated squaring; causes flickering / black textures on real content (fp16 squaring overflows to inf/NaN for bases >1). |

**Use ULTRA-v1** (v1 and v2 are the same fp16 driver, 16330280). ULTRA-v3 added
`pow()` repeated-squaring for a lighting-microbench win but it flickers/blacks textures
in real games, so it was rolled back - the deployed GammaOS build ships the v1 driver.

## What ULTRA does
- **multiview forced -> Vulkan 1.3** (153 device extensions) instead of the stock
  blob's frozen Vulkan 1.1 (71). This is what lets DXVK / VKD3D (Winlator, Box64)
  and newer Vulkan emulators run at all.
- fragment shaders opt into 128-wide (double-threadsize) waves;
- UBWC framebuffer compression disabled (a measured net loss on this GPU);
- constant-coefficient FMA-chain reassociation (matches the stock compiler, brings
  compute from 52 to stock-parity 127-129 GFLOPS);
- forced fp16 fragment math (large win on realistic fragment shaders; lossy);
- constant-integer `pow(x, N)` (specular exponents) lowered to a repeated-squaring
  fmul chain instead of the fp32-only exp2/log2 SFU pair (+20% on fp16 lighting).

## Test results (RG 55G1, Adreno 613 @ 1010 MHz, device-validated)

Numbers are for the recommended **ULTRA v1/v2** driver (fp16-only, 16330280).
3DMark (real titles), higher is better:

| Test | Stock Adreno | dw_noubwc (v1) | ULTRA (v1/v2) |
|------|-------------:|---------------:|--------------:|
| Wild Life (1440p)          | 700 | 649 | **719** |
| Wild Life Extreme (4K)     | 174 | 167 | **184** |

Microbenchmarks (GFLOPS, GPU pinned):

| Bench | Baseline | ULTRA (v1/v2) | Delta |
|-------|---------:|--------------:|------:|
| Compute (gpubench)             | 127 (stock)       | 129  | stock parity (reassoc) |
| Realistic lighting (gamebench) | 8.0 (Turnip fp32) | 14.0 | **+75%** (forced fp16) |

Compute is compared against the stock Adreno blob (reassociation reaches parity);
the lighting row is vs the same Turnip build with fp16 disabled (`GAMMA_NOFP16`),
isolating the fp16 lever.

ULTRA v1/v2 renders 3DMark Wild Life and Wild Life Extreme cleanly (screenshot-verified:
no banding, no black-frame corruption) and beats stock on every real title measured;
dw_noubwc (v1) reaches ~93-96% of stock while adding the modern-Vulkan surface.

> **Not ULTRA v3.** v3 added a constant-integer `pow()` -> repeated-squaring pass that
> scored higher on the lighting microbench (16.8 GFLOPS, +110% vs fp32) but caused
> flickering / black textures on real games (the fp16 squaring overflows to inf/NaN for
> bases >1). It was rolled back; the shipped driver is v1/v2.

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
