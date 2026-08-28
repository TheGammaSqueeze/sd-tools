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
| `GammaOS-Turnip-Adreno613-ULTRA-v3.adpkg.zip` | + forced fp16 + pow-squaring | **Recommended.** Everything above plus forced fp16 fragment math and constant-integer `pow()` lowered to repeated squaring. Fastest; fp16 is lossy. |

ULTRA-v1/v2 are earlier ULTRA revisions; **v3 is the current, device-validated
ULTRA** (adds the `pow()` -> repeated-squaring lowering). Use v3.

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

3DMark (real titles), higher is better:

| Test | Stock Adreno | dw_noubwc (v1) | ULTRA v3 |
|------|-------------:|---------------:|---------:|
| Wild Life (1440p)          | 700 | 649 | **723** |
| Wild Life Extreme (4K)     | 174 | 167 | **186** |

Microbenchmarks (GFLOPS, GPU pinned):

| Bench | Baseline | ULTRA v3 | Delta |
|-------|---------:|---------:|------:|
| Compute (gpubench)             | 127 (stock)         | 129  | stock parity (reassoc) |
| Realistic lighting (gamebench) | 8.0 (Turnip fp32)   | 16.8 | **+110%** (fp16 + pow-squaring) |
| `pow(x,32)` lowering, of which | 14.0 (fp16, exp2/log2) | 16.8 | **+20%** from repeated squaring |

Compute is compared against the stock Adreno blob (reassociation reaches parity);
the fragment rows are vs the same Turnip build with the optimization disabled
(`GAMMA_NOFP16` / `GAMMA_NOFASTMATH`), isolating each lever.

ULTRA v3 renders 3DMark Wild Life and Wild Life Extreme cleanly (screenshot-verified:
no banding, no black-frame corruption). dw_noubwc (v1) reaches ~93-96% of stock while
adding the modern-Vulkan surface; ULTRA v3 beats stock on every real title measured.

fp16 is lossy (reduced precision); most content renders correctly, but a title that
shows banding can opt out per-effect with `GAMMA_NOFP16` (fp16) / `GAMMA_NOFASTMATH`
(reassociation + pow-squaring).

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
