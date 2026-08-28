# GammaOS Turnip driver package (Adreno 613) for Winlator / AdrenoTools

`GammaOS-Turnip-Adreno613-v1.adpkg.zip` is a custom Vulkan driver package in the
AdrenoTools / Winlator format (flat zip: `meta.json` + `vulkan.turnip.so`), the same
layout as the Anbernic and community Turnip packages.

## What it is
The best self-built Mesa Turnip tuned for the Adreno 613 (gen6_3 / SG4250P), the
same driver documented in `docs/14-benchmarks.md` (`dw_noubwc`):
- multiview forced so it advertises **Vulkan 1.3** (153 device extensions) instead
  of the stock blob's frozen Vulkan 1.1 (71) - this is what lets DXVK / VKD3D
  (Winlator, Box64) and newer Vulkan emulators run;
- fragment shaders opt into 128-wide (double-threadsize) waves;
- UBWC framebuffer compression disabled (a measured net loss on this GPU, +7%).

Reaches ~93-96% of the stock Adreno driver in real titles (3DMark Wild Life
649 vs 700, Wild Life Extreme 167 vs 174) while adding the modern-Vulkan surface.

## How to use
In Winlator (or GameHub / any AdrenoTools-based loader): Contents / Video / Graphics
Driver -> import / add driver -> select this .zip -> pick it as the Turnip driver.
Then set the container's GPU driver to Turnip. Works on Android API 31+ (built
against API 31; the RG 55G1 is API 34).

Rebuild: the driver is `gpu/turnip-selfbuilt/vulkan.turnip.dw_noubwc.so`; the three
source patches are `turnip-noubwc-default.patch`, `turnip-fs-double-threadsize.patch`,
and the multiview change (see docs/14). Repackage with
`zip -j GammaOS-Turnip-Adreno613-v1.adpkg.zip meta.json vulkan.turnip.so`.
