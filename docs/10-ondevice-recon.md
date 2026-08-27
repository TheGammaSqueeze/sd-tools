# On-device recon (adb, no root) and corrections

Live data from the physical unit over adb. This corrects a core assumption: the
package supports three SoCs and I had been treating Parrot as the likely target;
the actual device is **RavelinP**.

## Device identity (measured)

| property | value |
|----------|-------|
| model | Anbernic **RG 55G1** (`ro.product.model = RG 55G1`) |
| SoC | **SG4250P / SG_RAVELINP**, `soc_id 654` (`ro.soc.model=SG4250P`, `/sys/devices/soc0/machine=SG_RAVELINP`) |
| platform name | `ro.board.platform = parrot` (family name only, not the SoC) |
| Android | **14** (`ro.build.version.sdk = 34`), build `V3.0.8` / `UKQ1.240913.001`, patch 2024-09-05 |
| kernel | `5.10.209-android12-9` GKI |
| bootloader | **UNLOCKED** (`verifiedbootstate: orange`, `flash.locked: 0`, `vbmeta.device_state: unlocked`) |

So this is a Ravelin-class part (Adreno 613 / "Adreno A12"), not the Parrot
(Adreno 710) I had also analyzed. My Ravelin DTB decode is the one that applies to
this hardware; the Parrot / Adreno 710 (940 MHz) analysis is for a different SoC
in the multi-target package that this unit does not use.

Flashing is viable: the bootloader is unlocked, so the repack + verification-
disabled-vbmeta + fastboot flow (docs/05, docs/09) will work here.

## CPU (the live EPSS LUT)

This validates the docs/06-07 conclusion that the CPU operating-point table is
runtime state, not a static file. The actual exposed frequencies:

- Little cluster: **6x Cortex-A55** (`CPU part 0xd05`), cpu0-5 (policy0), up to
  **1958.4 MHz**. Steps (kHz): 499200 672000 806400 921600 1094400 1286400
  1478400 1632000 1804800 1958400.
- Big cluster: **2x Cortex-A78** (`CPU part 0xd41`), cpu6-7 (policy6), up to
  **2400 MHz**. Steps (kHz): 691200 960000 1190400 1344000 1497600 1651200
  1900800 2054400 2131200 2208000 2304000 2400000.

The lval encoding holds: 2400000 kHz = 125 x 19.2 MHz; 1958400 = 102 x 19.2 MHz.
These are the values the EPSS hardware LUT was programmed with by XBL. Editing
them (CPU OC) still requires the firmware/runtime routes in docs/07, but now the
real ceiling is known: little 1958 MHz, big 2400 MHz.

## GPU (matches the Ravelin decode exactly)

- `gpu_model = AdrenoA12v1`; GLES string `Adreno (TM) A12, OpenGL ES 3.2
  V@0615.91 (GIT@a63fb93269 ... Date:08/27/24)`.
- 7 pwrlevels, `default_pwrlevel 6` (boots at 340 MHz), max **1010 MHz**.
- `gpu_available_frequencies`: 1010 / 955 / 850 / 765 / 605 / 500 / 340 MHz.

This is exactly the Ravelin (Adreno 613) table decoded in docs/04
(0x3C336080=1010, 0x38EC24C0=955, 0x32A9F880=850, 0x2D98F940=765, 0x240F9140=605,
0x1DCD6500=500, 0x1443FD00=340). So the GPU overclock target for THIS device is
the 1010 MHz Ravelin table; `add_gpu_level.py` on the Ravelin trees (validated at
1080 MHz) is the right tool, not the Parrot path.

## Graphics driver in use

- Stock Qualcomm `vulkan.adreno.so` / `libGLESv2_adreno.so`, driver **V@0615.91**
  (the same version extracted from the package, docs/09). No Turnip active
  (`game_driver_all_apps` unset, no injected `.so`).
- `ro.hardware.vulkan = adreno`, `ro.hardware.egl = adreno`.

Turnip implication corrected: the device runs **Android 14 (sdk 34)**, so the
Anbernic Turnip's `minApi 34` is correctly targeted (my earlier "minApi 34 vs
Android 12" concern came from the debug package's Android-12 vendor image, not the
running OS). Our own build targets API 31, which runs fine on API 34 (forward
compatible); rebuilding at API 34 is optional. The GPU is "Adreno A12", which is
in Turnip's supported marketing list, and the KGSL kernel (5.10.209) passed the
ioctl compatibility check (docs/09), so Turnip is expected to load here.

## What still needs on-device testing (no root limits this pass)

- Load our Turnip via AdrenoTools and A/B against the blob (needs an app that
  supports custom drivers, or root for the system swap).
- The GPU overclock (flash a Ravelin vendor_boot with a raised/added pwrlevel and
  confirm `gpu_available_frequencies` shows the new top and it is stable).
- Fuse state for firmware mods: `fastboot oem device-info` (bootloader is
  unlocked, which is the part that gates flashing).
