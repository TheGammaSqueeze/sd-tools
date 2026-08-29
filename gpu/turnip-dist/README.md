# GammaOS Turnip driver packages (Adreno 613) for Winlator / AdrenoTools

Custom Vulkan driver packages in the AdrenoTools / Winlator format (flat zip:
`meta.json` + `vulkan.turnip.so`), the same layout as the Anbernic and community
Turnip packages. All are self-built Mesa Turnip tuned for the Adreno 613 (gen6_3 /
SG4250P, stock clock 1010 MHz) and documented in `docs/14-benchmarks.md`.

## Packages

| Zip | Build | Notes |
|-----|-------|-------|
| `GammaOS-Turnip-Adreno613-ULTRA-v4.adpkg.zip` | selective fp16 | **Recommended - the shipped GammaOS driver.** dw_noubwc (multiview VK1.3 + 128-wide waves + UBWC-off) + FMA reassociation + selective forced fp16 (texture-coord/depth chains kept fp32 so textures do NOT go black). Fast and renders correctly. |
| `GammaOS-Turnip-Adreno613-GameNative-flushall-v1.adpkg.zip` | ULTRA-v4 + flushall | **For emulators (GameNative/Winlator).** Adds a baked cache-flush coherency workaround for DXVK/VKD3D/RPCS3 render-to-texture. Fixes corruption in some titles (e.g. MGS4). |
| `GammaOS-Turnip-Adreno613-GameNative-sysmem-v1.adpkg.zip` | ULTRA-v4 + sysmem | **For emulators.** Renders direct-to-sysmem (bypasses GMEM tiling); faster than flushall on RT-heavy content. A/B against the flushall build for your title. |
| `GammaOS-Turnip-Adreno613-AGGRESSIVE-v1.adpkg.zip` | no fp16 | dw_noubwc + FMA reassociation, no forced fp16. 100% safe (no fp16 artifacts), ~10% slower than ULTRA on ALU-bound titles. |
| `GammaOS-Turnip-Adreno613-v1.adpkg.zip` | dw_noubwc (strict) | multiview VK 1.3 + 128-wide fragment waves + UBWC-off. Closest to reference precision. |
| `GammaOS-Turnip-Adreno613-ULTRA-v1.adpkg.zip` | blanket fp16 | **Superseded.** Forces fp16 on ALL fragment math including texture coordinates -> black textures on some content (e.g. MGS4). Use ULTRA-v4 (selective) instead. |
| `GammaOS-Turnip-Adreno613-ULTRA-v3.adpkg.zip` | + pow-squaring | **DEPRECATED - do not use.** `pow()` repeated-squaring flickers / blacks textures (fp16 overflow to inf/NaN for bases >1). |

**Use ULTRA-v4** (selective fp16, driver 16338592) for general use - it is the shipped
GammaOS driver. For emulators (GameNative/Winlator running DXVK/VKD3D/RPCS3, e.g. MGS4)
use the GameNative-flushall or GameNative-sysmem variant. The older blanket-fp16 ULTRA-v1/v2
(16330280) and the pow-squaring ULTRA-v3 both cause black textures and are superseded.
If you see any fp16 artifact even on v4, fall back to AGGRESSIVE (no fp16, ~10% slower).

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

Numbers are for the recommended **ULTRA-v4** driver (selective fp16, 16338592).
3DMark (real titles), higher is better:

| Test | Stock Adreno | AGGRESSIVE (no fp16) | ULTRA-v4 (selective fp16) |
|------|-------------:|---------------------:|--------------------------:|
| Wild Life (1440p)          | 700 | 649 | 650 |
| Wild Life Extreme (4K)     | 174 | 167 | **179** |

Microbenchmarks (GFLOPS, GPU pinned):

| Bench | Baseline | ULTRA-v4 | Delta |
|-------|---------:|---------:|------:|
| Compute (gpubench)             | 127 (stock)       | 129  | stock parity (reassoc) |
| Realistic lighting (gamebench) | 8.0 (Turnip fp32) | 14.0 | **+75%** (forced fp16) |

Compute is compared against the stock Adreno blob (reassociation reaches parity);
the lighting row is vs the same Turnip build with fp16 disabled, isolating the fp16 lever.

ULTRA-v4 renders 3DMark Wild Life and Wild Life Extreme cleanly (screenshot-verified: no
black textures) and beats stock on WLE (179 vs 174). The fp16 benefit is workload-
dependent: it is +75% on ALU-bound lighting and roughly full on emulator/fragment-ALU
content, but ~zero on texture-bound Wild Life (650 vs 649 aggressive) because the fp16 win
there was texture-coordinate math that selective fp16 now protects to avoid black textures.
The older blanket-fp16 ULTRA-v1/v2 scored higher on Wild Life (719) precisely because it
did NOT protect those coords - which is what made textures go black. dw_noubwc reaches
~93-96% of stock while adding the modern-Vulkan surface.

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
