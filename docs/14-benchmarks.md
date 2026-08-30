# Overclock stress-test and benchmark campaign (RG 55G1 / RavelinP)

> **Current status (2026-08-29): the shipped Turnip driver is ULTRA v1/v2 (fp16-only,
> 16330280)** = dw_noubwc (multiview VK1.3 + fragment wide-wave + UBWC-off) + constant-FMA
> reassociation + forced fp16 fragment math. Real-title scores: 3DMark Wild Life **719**
> (stock 700), Wild Life Extreme **184** (stock 174), +75% on the fp16 lighting microbench;
> renders correctly.
> **ULTRA v3 (pow-squaring, 16337896) was ROLLED BACK** - it flickers / blacks textures on
> real games (the fp16 repeated-squaring for pow(x,N) overflows to inf/NaN for bases >1).
> Its pow-squaring pass is now opt-in only (`GAMMA_POWI` env, never default). This file is a
> chronological research log; where earlier entries call the pow-squaring build "deployed",
> that is superseded by this banner and the final rollback entry.

Goal: push GPU / CPU / MEMORY as high as possible while staying stable, measured
against a stock-max baseline. Device runs GammaOS Next Lite (rooted). All runs
use `scripts/bench/` with fan at max (`persist.gammaos.fan_mode=max`) and thermal
throttling stopped, everything pinned to its max OPP.

## Harness

- `scripts/bench/device_setup_maxperf.sh` - fan max, stop thermal-engine, CPU
  governor=performance with `scaling_min=scaling_max` on both clusters, GPU
  `min_pwrlevel=max_pwrlevel=0` + `force_clk_on`.
- `scripts/bench/device_run_bench.sh` - runs the three microbenchmarks and reports
  clocks + temps.
- `scripts/bench/run_on_device.sh <label>` - host wrapper: push, setup, run, save
  to `bench/results/<label>.txt`.
- Microbenchmarks (aarch64, `scripts/bench/src/`):
  - `cpubench` - fixed-work integer+FP loop, `mops` (higher = faster). Pin with
    `taskset f0` (big A78 cluster) / `taskset 0f` (little A55 cluster).
  - `membench` - DDR streaming read + copy bandwidth (GB/s) and random-cycle
    pointer-chase latency (ns).
  - `gpubench` - Vulkan compute FMA kernel, reports GFLOPS (also a GPU stability
    probe). 32768 groups is the safe size (65536 triggers a device-lost).

## Running the campaign

`scripts/bench/campaign.sh` orchestrates both modes against an online rooted
device and writes labelled, parseable results under `bench/results/<label>/`:

```
scripts/bench/campaign.sh run baseline 120     # per-component + 120s combined
scripts/bench/campaign.sh run gpu_oc_1100 120  # after applying the GPU OC
scripts/bench/campaign.sh table                # regenerate the tables below
```

Each `run` pushes the tools, applies `device_setup_maxperf.sh` (fan max via the
real gpio-pwm node, thermal-engine stopped, every OPP pinned to max), runs the
per-component bench (mode B) and the combined all-max stress (mode A), and saves
`percomponent.txt` + `combined.txt` + `state.txt`. `campaign.sh table` runs
`parse_bench.py`, which computes each non-baseline label's delta against the
`baseline` run and the combined-stress sustained clocks / peak temp / survival.

## Stock-max baseline

Pinned to stock max OPPs (CPU big 2400 MHz, little 1958.4 MHz, GPU 1010 MHz),
fan max, thermal off. `bench/results/baseline/baseline_stockmax.txt`.

| Component | Metric | Baseline |
|-----------|--------|----------|
| CPU big (2x A78 @2400 MHz) | cpubench mops | 298.2 |
| CPU little (6x A55 @1958.4 MHz) | cpubench mops | 84.1 |
| MEM | read GB/s | 15.3 |
| MEM | copy GB/s | 37.8 |
| MEM | latency ns | 127.0 |
| GPU (Adreno A12/613 @1010 MHz) | gpubench GFLOPS | 129.2 |
| Thermals | max zone under load | ~38 C (cool, fan max) |

GPU driver in use for the bench: stock Qualcomm `Adreno (TM) A12`, Vulkan 1.1.128
(v0615.91). Driver swap (Turnip) is deliberately deferred until all OC benchmarks
are done.

## Overclock results

Two modes: per-component (each vs its baseline max) and combined (all at max
simultaneously). Filled in as the campaign proceeds; raw logs under
`bench/results/`.

| Run | GPU MHz | CPU big MHz | GPU GFLOPS | CPU big mops | MEM copy GB/s | max temp | stable? |
|-----|---------|-------------|-----------|--------------|---------------|----------|---------|
| baseline (per-comp) | 1010 | 2400 | 129.1 | 298.8 | 35.8 | 40 C | yes (stock) |
| baseline (combined all-max 90s) | 1010 | 2400 | - | held | held | 50.4 C | yes, 0 worker fails |

Baseline re-captured device-confirmed on a28c0e0e: CPU big 298.8 mops @2400, CPU
little 84.1 mops @1958.4, MEM read 15.1 / copy 35.8 GB/s @126 ns, GPU 129.1 GFLOPS
@1010, fan 255 (~3900 rpm), thermal off. Combined all-max 90s held every clock at
max, peak 50.4 C, no worker failures.

**Runtime OC knobs are exhausted on this GSI.** GPU: capped at 1010 (silicon/ACD,
see below). CPU: EPSS LUT is the only lever and needs `/dev/mem` which is compiled
out (docs/07) -> needs an ioremap kernel module. MEM: there is NO CPU-DDR devfreq
node (only ufshc + GPU busmon), so DDR frequency is entirely RPMh/AOP-firmware
managed with no runtime handle -> a DDR OC needs editing the AOP/BCM vote table or
DDR training in firmware (deep, EDL-recovery risk). Net: no component can be
stably overclocked from userspace; further gains require a kernel module (CPU) or
deep firmware reflash (GPU GMU-ACD, MEM AOP/DDR).

`a662_gmu.bin` was reverse-inspected to close the GMU avenue: it is a block table
(records `{u32 addr; 0; type=1; u32 size}`) of GMU processor CODE (strings
`GmuMain`, `GmuPwrStart`, `GmuPwrGxBwVote`, `EcpRecoverFromFault`, ...), unsigned
(deadbeef tail, no MBN footer), with NO freq/DCVS/ACD table inside — those are
delivered to the GMU at runtime over HFI from the DTB pwrlevels. So the GMU blob
has no tunable table to patch; changing GPU DVFS behaviour there would mean
rewriting the GMU RISC firmware. The DTB-side levers (freq, RPMh corner) are the
only GMU-adjacent knobs, and both are exhausted.

Bottom line for this unit: the stable operating point is the stock max
(GPU 1010 / CPU 2400+1958.4 / DDR stock). The accessible OC surface is fully
characterized and exhausted; the only unexplored paths are (a) a hand-built
android12-5.10 GKI ioremap module to poke the EPSS CPU LUT (needs the GKI kernel
source / Module.symvers, currently unavailable), and (b) deep XBL/AOP DDR-training
or GMU-RISC firmware reflashes (high risk, EDL-recovery).

## Exhaustive GPU-OC avenue exploration (device-confirmed)

Every accessible lever was tested against the forced-pin stress:

1. Clock (in-place gpucc top entry): works, GPU clocks to 1040/1100.
2. Stable ceiling: **hard wall at exactly 1010** - even +30 MHz (1040) resets the
   SoC instantly under load. 1050/1100 likewise.
3. Voltage corner (DTB `qcom,gpu-pwrlevel@0 { qcom,level }`): TURBO_L1 0x1a0 ->
   TURBO_L3 0x1e0 -> SUPER_TURBO 0x1ff, with DTB freq matched to the module clock:
   no effect, resets just as fast.
4. GX rail: the GPU `vdd`/`vddcx` supplies are GDSCs (`gpu_cc_gx_gdsc` /
   `gpu_cc_cx_gdsc`, power-domain switches), not voltage rails. The GX voltage is
   GMU-owned via RPMh and is not readable/forcible from Linux; `qcom,level` is the
   only input to the GMU's vote and it is maxed.
5. ACD: disabled and unconfigured (`acd`=0, empty `acd/`/`lm/`, no
   `qcom,gpu-acd-table`), can't enable at runtime, needs unavailable silicon
   calibration.
6. Fault path: the reset is a hard power collapse with no software fault logged
   (captured via console-ramoops), consistent with the GMU refusing to power the
   GX above 1010 rather than a recoverable GPU fault.

Conclusion: the **GMU firmware hard-caps the GX at 1010**. `a662_gmu.bin` is ARM
Thumb-2 GMU-processor code (block table `{addr,0,type=1,size}` -> code at GMU
0x4000, unsigned). It embeds frequency constants 1000 MHz and 1040 MHz at GMU
vaddr 0x4a64/0x4a6c (file 0xc80/0xc88). The ONLY remaining GPU-OC lever is to
reverse the Thumb-2 DCVS/clamp logic around those constants and patch the cap,
then redeploy the GMU blob (it lives in /vendor/firmware, so needs a vendor-image
reflash or a firmware_class.path override) and retest. High effort, real brick
risk if the GMU fails to init; the silicon is also a low bin (Adreno613v1) that
may not run higher stably even if the cap is lifted. Parked pending an explicit
go-ahead for the GMU-firmware RE.


### GMU firmware: no patchable constant (analysis done)

Followed the GMU-RE lead to a conclusion. `a662_gmu.bin` (Thumb-2, unsigned) has
NO simple patch target for the 1010 cap: the 1000/1040 "MHz" values are ns
timeouts (1.0s/1.04s), not a freq clamp, and there is no max-corner constant
either (0x1a0/TURBO_L1 never appears; the 0x100/0x200 hits are the block-header
table). The GMU's frequency/voltage limit is algorithmic (its DCVS state machine
plus the AOP-defined GX-corner availability), not a single editable value. So a
GMU-firmware OC would require reverse-engineering and rewriting the Thumb-2 DCVS
logic (large effort, high brick risk if GMU init breaks) - parked pending an
explicit go-ahead. Net: no accessible or tractable lever raises the GPU above
1010 on this unit.

CPU: no accessible lever at all - no `/dev/mem` (CONFIG_DEVMEM off, even under
permissive), no rpmh/opp/regmap/clk register debugfs, no cpufreq OPP above 2400,
and building the ioremap EPSS module needs the GKI kernel source (network-blocked).
MEM: no cpu-ddr devfreq node; DDR is RPMh/AOP-firmware managed with no runtime
handle.
| gpu in-place 1050 | 1050 | - | - | - | - | - | no (SoC reset under sustained load) |
| gpu in-place 1100 | 1100 | - | - | - | - | - | no (SoC reset under sustained load) |

GPU OC status: the in-place method reaches 1050/1100 MHz cleanly (boots, clocks,
no probe crash) but neither is stable under sustained load at the stock voltage
corner, so the stable GPU ceiling is 1010 without a GMU/voltage change. See the
GPU-overclock section below for the full method, the append-crash to avoid, and
the stability table. CPU OC is blocked (no `/dev/mem`, see docs/07); MEM OC not
yet attempted.

## GPU overclock: the lever is the gpucc module, and you must edit IN PLACE

The GPU clock is capped at 1010 by the freq table compiled into
`/vendor_dlkm/lib/modules/gpucc-ravelin.ko` (symbol `ftbl_gpu_cc_gx_gfx3d_clk_src`),
NOT the DTB. `clk_rcg2` round_rate picks the highest table entry `<=` the request,
so a DTB-only pwrlevel rounds back to the 1010 table entry. The gfx3d RCG is
`clk_rcg2_ops` fed by `clk_alpha_pll_lucid_evo_ops` (a fractional PLL), so the
table entry is what sets the achievable rate. Table format: 24-byte stride,
`{ u64 freq; u8 src=0x03; u8 pre_div=0x03; u16 m=0; u16 n=0; u64 pad=0 }`
(pre_div 0x03 = post-divide by 2). Stock top entry is 1010 MHz (0x3c336080).
`CONFIG_MODULE_SIG` is off and `sig_enforce=0`, so a byte-patched module loads.

### DO NOT append entries. Edit the existing top entry in place.

APPENDING new freq entries (1050/1100/1150/1200) into the table's trailing zero
padding **kernel-panics at module load**, device-confirmed via console-ramoops:

```
Unable to handle kernel paging request at virtual address 0x0200000046868b00
ESR = 0x96000005  (data abort, translation fault)   Comm: modprobe
  __clk_register+0x1d4/0x7c0
  devm_clk_register_regmap+0xac [clk_qcom]
  qcom_cc_really_probe+0x3f8/0x4dc [clk_qcom]
  gpucc_ravelin_probe+0x9c/0xcc [gpucc_ravelin]
```

Growing the table corrupts the clock registration (a garbage pointer built from an
injected freq value), so `gpucc_ravelin_probe` -> `qcom_cc_really_probe` ->
`__clk_register` dies. A bisection proved it: the SAME debugfs repack with the
UNMODIFIED module boots fine, so it is the table growth, not the repack/verity.

The safe method is to change ONLY the existing top entry's 8-byte freq value in
place (same entry count, same layout). `tools/fw/gpucc_oc.py --in-place <MHz>`
does this. Device-confirmed: the in-place module loads with no probe crash, and
KGSL picks up the new rate directly (`max_gpuclk` and `gpu_available_frequencies`
top both become the new value even with the stock DTB), and `gpuclk` reads the
new rate under load. No DTB pwrlevel edit is needed.

### Stability (stock voltage corner)

Device-confirmed on the RG 55G1:

| top OPP | corner | boots | forced-pin sustained load (32768 groups x8192 x4) |
|---------|--------|-------|--------------------------------------------------|
| 1010 (stock) | 0x1a0 TURBO_L1 | yes | **stable** (~129 GFLOPS, held 1010, no reset) |
| 1050 in-place | 0x1a0 | yes | SoC reset |
| 1100 in-place | 0x1a0 | yes | SoC reset |
| 1100 in-place | 0x1e0 TURBO_L3 (voltage bump) | yes | SoC reset (no improvement) |

Method validated by control: stock 1010 survives the exact forced-pin stress that
resets the OC levels, so the instability is real, not a test artifact (all
self-recover on reboot because the in-place module still probes cleanly). Raising
the GPU top pwrlevel's RPMh corner from TURBO_L1 (0x1a0) to TURBO_L3 (0x1e0) in
the DTB gave the OC more GX voltage but did NOT help 1100 — it reset just as fast.
That rules out simple GX rail voltage as the limiter. Investigating further:
ACD (Adaptive Clock Distribution, the mechanism that lets Adreno hold higher
clocks by compensating voltage droop) is **entirely disabled and unconfigured**
on this unit: `/sys/class/kgsl/kgsl-3d0/acd` reads 0 and won't flip at runtime,
the `acd/` and `lm/` sysfs dirs are empty, and there is no `qcom,gpu-acd-table`
in the DTB. Enabling it properly would need silicon-specific ACD calibration
coefficients (from fuses/characterization) that aren't available, and this part
is a low bin (`qcom,gpu-model = "Adreno613v1"`, GPU firmware A662/gen6_3_26_0,
`a662_gmu.bin`). The GMU `.bin` is GMU processor code; the freq/DCVS tables are
sent at runtime via HFI from the DTB pwrlevels (which we already control), so
there is no freq gate to patch in the blob. Net: the two accessible firmware
levers (RPMh voltage corner, ACD enable) are exhausted, and **the stable GPU
ceiling on this unit is 1010** on static margin. The DTB voltage-corner lever is
`qcom,gpu-pwrlevel@0 { qcom,level }` (0x1a0=TURBO_L1 .. 0x1e0=TURBO_L3 .. 0x1ff
SUPER_TURBO) if revisiting later with ACD calibration data.

### Deployment (bypassing verity for the modified vendor_dlkm)

vendor_dlkm is ext4, dm-verity, `avb` anchored in the main `vbmeta`. The debugfs
edit leaves a stale hashtree, so verity must be off. The clean, device-confirmed
way is patched boot images built from the LIVE `lun6_*` dumps with the AOSP dtc
(`AOSP_DTC=prebuilt/dtc-aosp-x86_64`, never the host dtc, which mangles
`qcom,gpu-freq`): `boot`+`vendor_boot` carry `enforcing=0
androidboot.selinux=permissive audit=0`, and the vendor_boot first-stage fstab has
every `avb`/`avb=vbmeta_system`/`avb_keys=` flag stripped (keys kept). Then a
modified `vendor_dlkm` mounts as plain ext4 and boots. Always flash via fastbootd
(`adb reboot fastboot`), not bootloader fastboot (rejects `vendor_boot` writes).

### Diagnosing boot hangs: enable console-ramoops

This unit's stock ramoops has `console_size=0`/`record_size=0` (pmsg only), so
kernel panics are not captured. To debug, edit the vendor_boot DTB `ramoops` node
(all 15 concatenated DTBs) to carve `console-size = <0x100000>`, `record-size =
<0x20000>`, `max-reason = <0x05>`, shrinking `pmsg-size` to `<0x80000>`; repack
with the AOSP dtc. After a crash, `mount -t pstore pstore /sys/fs/pstore` and read
`console-ramoops-0` / `dmesg-ramoops-0`. Patcher and images: `/work/55g1/gpucc/`,
`/work/55g1_patched/`.

## Fan control (important)

The RG 55G1 fan is a gpio-pwm (`gpio-pwm.ko`, DT node `soc/gpio_pwm`, pinctrl
`fan_pwm_active`), NOT the `persist.gammaos.fan_mode` property. That prop is dead
on the bvN GSI because the GSI does not carry the device-specific GammaOS fan
service. Control it directly (root):

```
echo 255 > /sys/class/gpio_pwm/duty     # 0-255, 255 = full speed
cat  /sys/class/gpio_pwm/speed          # tachometer RPM readout (read-only)
```

At duty 255 the fan runs ~7500-7900 RPM. Duty tracks speed; writes outside 0-255
return EIO. The bench setup drives this; `scripts/bench/device_fan.sh <0-255>` is
a standalone helper. Found by tracing the DT `gpio_pwm` node after the prop and
the PMIC LPG pwmchip0 both failed.

### msm_kgsl.ko is not the clamp; the AOP GX voltage table is the prime suspect

Tick analysis: pulled and inspected msm_kgsl.ko (aarch64, vendor_dlkm). It carries
the pwrlevel/corner/rail vote to the GMU faithfully (traces kgsl_gmu_pwrlevel,
kgsl_rail, kgsl_buslevel) - it does not clamp the corner, so patching KGSL will
not lift the wall. Since the DTB corner 0x1ff also had zero effect, the clamp is
BELOW KGSL. The most likely real limiter is the AOP/RPMh firmware's GX rail
(gfx.lvl) resource: if it only defines corners up to TURBO_L1 (0x1a0), any higher
vote (TURBO_L3/SUPER_TURBO) clamps to the same voltage, so the OC frequency runs
undervolted and the SoC browns out - which matches the observed hard power
collapse with no software fault. Confirming/lifting this needs reversing and
editing the GX voltage table inside aop.mbn (deep, re-sign with the vendored
SecTools test keys, EDL-recovery risk) - the deepest lever, parked for explicit
go-ahead. No non-destructive lever remains that raises GPU voltage above stock.

### ROOT CAUSE (definitive): the AOP power tables cap every rail at TURBO_L1

Reversed the AOP cmd-db / RPMh ARC tables inside the `aop_a` partition (the GX
corner voltages live here, not in the GMU or DTB). Every ARC rail's supported-
corner array is: `00 10 40 80 c0 100 140 180 1a0 00` (OFF, RETENTION, LOW_SVS,
SVS, SVS_L1, NOM, NOM_L1, TURBO, **TURBO_L1**, zero-terminated). NO rail - gfx
included - defines any corner above TURBO_L1 (0x1a0). That is the exact clamp: the
DTB votes of TURBO_L3 (0x1e0) / SUPER_TURBO (0x1ff) had zero effect because those
corners do not exist in the platform's tables, so RPMh clamped them to 0x1a0. The
GPU is stable at its maximum frequency (1010) for the maximum GX voltage the
platform defines (TURBO_L1), and every OC above that runs undervolted -> hard SoC
brownout, exactly as observed.

Because NOT A SINGLE rail on this PMIC (pm6450) uses a corner above TURBO_L1, the
PM6450 SMPS almost certainly has no higher GX voltage programmed either - so
adding a corner to the gfx array in the AOP would not deliver more volts; it would
just be a hard-brick-risk AOP re-sign + flash (AOP is pre-fastboot; recovery = EDL)
for a gain the hardware/platform is not built to supply. This is a firmware/PMIC
platform limit, not merely a low silicon bin. **Conclusion: GPU OC beyond 1010 is
not achievable on this device without a PMIC-level voltage-table change (deeper
than AOP, and physically bounded by the SMPS), which is beyond a safe software
mod.** The GPU-OC investigation is complete: the exact mechanism is identified and
the wall is a hard platform power limit.

## GPU driver: Turnip vs stock Adreno (measured) - Turnip is a regression here

Runtime bind-mount test (no flashing): `mount --bind vulkan.turnip.so over
/vendor/lib64/hw/vulkan.adreno.so`, then run gpubench in a fresh process so it
loads Turnip while the live UI stays on Adreno. Device-confirmed on a28c0e0e,
GPU pinned to 1010 MHz, same FMA compute workload (8192 groups x 2048 iters):

| Vulkan driver | reported device / api | GFLOPS @1010 | heavy dispatch (32768x8192) |
|---------------|-----------------------|--------------|------------------------------|
| stock Adreno (vulkan.adreno.so) | "Adreno (TM) A12" / 1.1.128 | **127.7** | stable |
| self-built Turnip (Mesa 26.3.0, a702) | "Turnip Adreno (TM) 613" / 1.0.359 | **52.1** | **VK_ERROR_DEVICE_LOST** |

Turnip correctly detects the real silicon (Adreno 613) and runs, but delivers
**2.45x LESS compute throughput at the same clock**, and it loses the device on
the large dispatches the stock driver handles fine. So a system-wide Turnip swap
(scripts/swap_vulkan_turnip.sh) would REGRESS GPU compute and add instability -
not recommended for performance on this unit. Turnip's value here would be
compatibility/features/newer-Vulkan (1.4) for specific apps, not raw throughput.
The bind-mount is fully reversible (umount); stock preserved at
gpu/stock-qualcomm/vulkan.adreno.so.

### Driver-variation sweep + display viability (device-confirmed)

Extended the driver comparison (all via the reversible bind-mount, GPU @1010):
- **Stock Adreno remains the compute leader (127.7 GFLOPS).** No alternative beat it.
- **Self-built Turnip = 52.1 GFLOPS**, unchanged by ir3/TU env knobs
  (IR3_SHADER_DEBUG=noopt, TU_DEBUG=noconform/forcebin) - the 2.45x gap is the ir3
  compute compiler, inherent, not a build flag. The build is already
  `-Dbuildtype=release` for the correct GPU (Turnip auto-detects Adreno 613).
- **Anbernic-shipped Turnip** (gpu/turnip-anbernic) fails to init under gpubench
  (no Vulkan device enumerated) - not usable here.
- **Turnip IS display-safe**: bind-mounted system-wide + restarted SurfaceFlinger,
  the UI rendered at full 1080x1920 with no SF/vulkan errors. This is because SF
  composites via **GLES** (libGLESv2_adreno), not Vulkan - a Vulkan-driver swap
  only affects Vulkan apps (games/emulators), never the base UI. (Note: SF holds
  the driver open, so a bind-mount needs `umount -l` + SF restart to revert.)

### CORRECTION: the "2.45x compute gap" is a benchmark artifact, not a Turnip deficit

Re-examined the 52 vs 128 gap by controlling how the kernel's multiply-add is
expressed. The original gpubench shader uses the expression `a = a*b + c` (a
separate multiply and add that a compiler MAY contract into one `mad`). Built a
second shader (`gpubench_fma`, source `scripts/bench/src/gpubench_fma.comp`) that
uses the canonical `a = fma(a,b,c)` intrinsic instead, and ran both shaders on
both drivers (GPU @1010, 8192x2048x5, device-confirmed):

| driver | `a*b + c` expression | `fma()` intrinsic |
|--------|----------------------|-------------------|
| stock Adreno | **126.4** | **53.7** |
| self-built Turnip | 52.0 | 52.1 |

Two facts fall out:
- On the **canonical `fma()` kernel the two drivers are within ~3%** (53.7 vs
  52.1). Turnip is **not** 2.45x slower at compute in a fair comparison - on true
  fused-multiply-add throughput it essentially matches the stock blob.
- Stock only reaches 126 on the `a*b + c` form: its compiler takes a fast
  contracted-`mad` path there that hits ~2x the rate of an explicit `fma()`, while
  Turnip's ir3 lowers both forms to the same ~52 code. So the headline gap was the
  stock compiler exploiting one specific expression pattern, not a general Turnip
  weakness. (The reproducible `fma()`-vs-`a*b+c` split is the honest measurement;
  the earlier "2.45x regression" over-stated it by using only the one form stock
  optimizes hardest.)

This is a real, narrow ir3 codegen opportunity (contract `fmul`+`fadd` -> `mad`
and match stock's dual-issue scheduling on the contracted form), not a 2.45x
platform deficit. Net corrected verdict: **stock still leads on this ALU
microbenchmark, but Turnip is a genuinely close (within ~3% on fair FMA), viable
driver for compute**, with its remaining advantage being newer Vulkan +
open-source compatibility. Bench artifacts committed: `gpubench_fma.comp` /
`.spv` / `_spv.h` / `gpubench_fma.c` under scripts/bench/src.

Verdict (raw peak): the stock Adreno driver still posts the highest single number
on this microbench via its contracted-mad path, so it stays the default; but the
gap is expression-specific, not a blanket 2.45x, and Turnip matches stock on
canonical FMA. Turnip's standing value is compatibility / newer Vulkan (1.4) for
specific titles. Turnip is kept in the tree
(gpu/turnip-selfbuilt) and can be deployed system-wide via
scripts/swap_vulkan_turnip.sh (bakes it into the vendor image at
/vendor/lib64/hw/vulkan.adreno.so) if a specific app needs it; stock is preserved
at gpu/stock-qualcomm/vulkan.adreno.so for instant revert.

### Turnip DEPLOYED system-wide (baked into /vendor, device-confirmed)

Per request, baked the self-built Turnip into the vendor partition and flashed it,
so it is now the persistent system Vulkan driver for all apps (games/emulators):
- Pulled the live vendor (`/work/55g1/vendor_live.img`, the stock backup), grew
  the ext4 into the partition's ~30 MB slack (the now-unused avb hashtree region),
  and `debugfs`-swapped `/vendor/lib64/hw/vulkan.adreno.so` for Turnip with the
  correct `same_process_hal_file:s0` context + 0644 (`/work/55g1/vendor_turnip.img`).
- Flashed via fastbootd (verity already disabled). Device boots in ~15 s, UI
  renders at full 1080x1920 (GLES composition, unaffected), and gpubench reports
  `Turnip Adreno (TM) 613` = every Vulkan app now uses Turnip.
- GLES/EGL stay on the Qualcomm blobs; only the Vulkan path changed.

Tradeoff (measured): Turnip gives newer Vulkan (1.4) and open-source
compatibility for the games/emulators this handheld runs, at ~52 vs ~128 GFLOPS
for raw FMA compute. Evaluate real titles; revert instantly with
`fastboot flash vendor /work/55g1/vendor_live.img` (stock backup preserved).

### Turnip stability = viable daily driver (device-confirmed on the deployed vendor)

With Turnip live as the system driver, swept compute loads to find the limit:
8192x2048, 16384x2048, 16384x4096, 32768x4096 all complete (~52 GFLOPS); only the
extreme 32768x8192 (268M invocations x 8192-iter loops) hits VK_ERROR_DEVICE_LOST.
Crucially the DEVICE_LOST is GRACEFUL: KGSL resets the GPU (reset_count 25->31) and
only the offending app dies - the DEVICE STAYS UP (boot_completed=1), unlike the
AOP-OC hard SoC reset. Real games never approach 32768x8192-scale single dispatches,
so Turnip is stable for actual use, with safe per-app GPU recovery on overload.
Net: Turnip is a safe compatibility daily driver; the only measured cost is raw FMA
compute throughput (~52 vs ~128), which does not represent game/emulator graphics.

## Graphics-path benchmark (gfxbench) - stock beats Turnip on graphics too

Built a Vulkan GRAPHICS microbenchmark (scripts/bench/src/gfxbench.c) - renders a
fullscreen triangle to an offscreen target, fragment shader does an FMA loop per
pixel, so it exercises the real graphics path (vertex assembly, rasterization,
fragment shading), unlike the pure-compute gpubench. Device-confirmed @1010:

| driver | fragment GFLOPS (1920x1080) | vs stock |
|--------|-----------------------------|----------|
| stock Adreno | **~77** | baseline |
| self-built Turnip | **~42** | 0.55x (1.8x slower) |

So stock Adreno beats Turnip on the GRAPHICS path too (1.8x), narrower than the
compute gap (2.45x) but the same direction. Combined verdict: **stock Adreno is
the faster driver on BOTH compute and graphics for this GPU** - Turnip is slower
across the board for raw throughput. Turnip's only advantage is compatibility /
newer Vulkan (1.4) for titles the stock 1.1 driver cannot run. For raw
performance, stock is optimal; Turnip is a compatibility choice. (Real games add
CPU-side/driver-overhead factors this microbench does not capture, but the GPU-side
throughput clearly favors stock.) Revert to stock:
`fastboot flash vendor /work/55g1/vendor_live.img`.

### The graphics gap IS real (unlike compute) - fma() vs mul+add is identical here

Applied the same expression-control test to the graphics path: built an `fma()`
fragment variant (`scripts/bench/src/gfxbench_fma.frag`, binary `gfxbench_fma`)
and compared it against the original `a*b + c` fragment shader on both drivers
(1920x1080, 512 iters, GPU @1010, device-confirmed):

| driver | fragment `a*b + c` | fragment `fma()` |
|--------|--------------------|------------------|
| stock Adreno | 76.8 | 77.4 |
| self-built Turnip | 42.3 | 42.4 |

Unlike compute, the mul+add-vs-fma() split makes **no difference** on the graphics
path for either driver (each is flat within ~1%). Why: the compute gap came from a
single-variable dependency chain where stock could take a contracted-mad fast path
(2x); this fragment loop interleaves four variables (a,b,c,d) so that special path
does not apply and both compilers lower it the same way. Result: the **~1.8x
fragment-throughput gap (77 vs 42) is a genuine Turnip ir3 fragment-path deficit,
not a benchmark artifact** - this is the real optimization target (the compute
"2.45x" was mostly artifact; the graphics 1.8x is not). For the games/emulators
this handheld actually runs (fragment-bound), stock's fragment path is ~1.8x
ahead, which is the number that matters. Next: chase the ir3 fragment codegen
(occupancy / precision / sync flags) or a real-title comparison (3DMark WLE
stock-vs-Turnip). Artifacts: `gfxbench_fma.frag`/`_frag.spv`/`_frag_spv.h`/`.c`
under scripts/bench/src.

## Turnip modified to run 3DMark Wild Life Extreme (Vulkan 1.1+ report)

3DMark's Wild Life Extreme (and other 4K/next-gen titles) refused to run under
Turnip with "no compatible GPU". Root cause: the vanilla Turnip on the Adreno 613
advertises **apiVersion 1.0.359**, but WLE requires **Vulkan 1.1**. The version is
gated in `src/freedreno/vulkan/tu_device.cc` by `tu_has_multiview()`:

```c
props->apiVersion = tu_has_multiview(pdevice) ? ... 1.3/1.4 ... : VK_MAKE_VERSION(1,0,...);
```

`tu_has_multiview()` returns `device->info->props.has_hw_multiview || TU_DEBUG(NOCONFORM)`,
and the Adreno 613 has `has_hw_multiview=false`, so Turnip drops to VK 1.0.
Multiview is otherwise fully emulated on a6xx via geometry shaders (Turnip sets
`multiview=true`/`multiviewGeometryShader`), so the 1.0 cap is a conformance-badge
decision, not a functional limit - proven by `TU_DEBUG=noconform` bumping the
report to 1.3.359 with `multiViewport=1`.

**Fix:** patched `tu_has_multiview()` to return `true` unconditionally (bakes the
NOCONFORM behavior in, no env var needed), rebuilt Turnip, and swapped it into the
vendor Vulkan HAL. Verified device-side with `scripts/bench/src/vkdump`:

| driver | apiVersion | multiViewport |
|--------|-----------|---------------|
| stock Turnip | 1.0.359 | 0 |
| modified Turnip (multiview forced) | **1.3.359** | **1** |

Deployed by debugfs-swapping `/vendor/lib64/hw/vulkan.adreno.so` in the vendor
image (`/work/55g1/vendor_turnip_mv.img`, e2fsck-clean, selinux
`same_process_hal_file:s0` + 0644 preserved) and flashing via fastbootd.
End-to-end result: **3DMark Wild Life Extreme accepted the GPU and completed** -
Overall score **156**, avg **0.94 FPS** at 3840x2160 (low as expected: WLE is a 4K
next-gen test and Turnip is ~1.8x slower than stock on graphics; the point is the
compatibility rejection is gone). Driver + meta saved at
`gpu/turnip-selfbuilt/vulkan.turnip.multiview.so` + `meta-multiview.json`. Revert
to stock Vulkan: `fastboot flash vendor /work/55g1/vendor_live.img`.

## Real-title comparison: 3DMark Wild Life Extreme, stock vs Turnip (device-confirmed)

The microbenchmarks are pure-ALU loops; real games are limited by texturing,
bandwidth, triangle setup, fixed-function and driver overhead too. So the decisive
"which driver is faster for actual games" test is a real title. Ran 3DMark Wild
Life Extreme (3840x2160, the built-in 4K next-gen benchmark) on BOTH drivers by
actually flashing each vendor image via fastbootd (a runtime bind-mount does NOT
reach zygote-spawned apps - they are in a different mount namespace - so the driver
must be baked into /vendor for an app to use it). GPU pinned to 1010, fan max:

| driver (flashed vendor) | WLE overall score | avg FPS | vs stock |
|-------------------------|-------------------|---------|----------|
| stock Adreno (vendor_live.img) | **174** | 1.05 | baseline |
| multiview Turnip (vendor_turnip_mv.img) | **156** | 0.94 | 0.90x (1.12x slower) |

**Key result: in a real game workload Turnip is only ~12% behind stock (174 vs
156), NOT the ~1.8x the graphics microbench implied.** The synthetic ALU-bound
fragment loop massively over-states the real gap, because a real 4K render spends
most of its time in texturing/bandwidth/fixed-function where Turnip is competitive,
not in back-to-back FMAs where stock's fragment ALU throughput leads. Both drivers
run WLE fine (the earlier "no compatible GPU" was purely Turnip's VK-1.0 report,
now fixed; stock always reported 1.1).

**Verdict for the GOAL:** stock remains the single fastest driver (best microbench
numbers AND +12% in a real title AND no DEVICE_LOST), so it is the performance
default. But Turnip is a genuinely viable driver - within ~12% on a real game -
with newer Vulkan (1.3/1.4) and open-source compatibility as its upside, far
closer than the microbenchmarks suggested. The device is left on the multiview
Turnip (the session's deployed driver); swap to stock for peak performance with
`fastboot flash vendor /work/55g1/vendor_live.img`, back to Turnip with
`fastboot flash vendor /work/55g1/vendor_turnip_mv.img` (both via fastbootd).

## Root of the fragment gap: stock uses the 2x FP16 ALU, Turnip does not

Chased WHY stock's fragment path leads. Built three fragment variants of the same
interleaved multiply-add loop and ran them on both drivers via bind-mount (1920x1080,
512 iters, GPU @1010, device-confirmed):

| fragment shader precision | stock GFLOPS | Turnip GFLOPS |
|---------------------------|--------------|---------------|
| fp32 (`float`) | 77.7 | 42.6 |
| mediump (`RelaxedPrecision`, 34 decorations verified in the SPIR-V) | **125.6** | 42.3 |
| explicit `float16_t` (GL_EXT_shader_explicit_arithmetic_types_float16) | **125.1** | 42.3 |

The tell: **stock speeds up ~1.6x when the shader drops to 16-bit (77 -> 125),
because the Adreno a6xx runs FP16 ALU at ~2x rate; Turnip stays pinned at ~42
GFLOPS at every precision** - fp32, mediump, AND explicit fp16 are all 42.3. So
Turnip is not engaging the 2x FP16 path at all on this workload (it computes even
declared-fp16 math at the single (fp32) rate), and its fragment ALU throughput is a
flat ~42 regardless of precision. Two independent stock advantages stack: a ~1.8x
base fp32 fragment-ALU lead, plus a ~1.6x FP16 multiplier Turnip does not capture,
so a pure mediump fragment loop is ~3x on stock (125 vs 42). Turnip DOES carry the
lowering machinery (`tu_shader.cc` `mediump_16bit_alu = true`, `ir3_nir.c`
`nir_lower_mediump_io`), so the miss is most likely that ir3 is not packing the
interleaved fp16 ops into the vec2 (half2) form that actually doubles a6xx FP16
rate - a deep ir3 scheduling limitation, not a driver build flag (rebuilding with
LTO/-O3 optimizes the CPU-side driver, not the GPU shader, so it cannot move these
numbers).

Why the real WLE gap was only 12% despite this: mobile games (and WLE) lean on
mediump, which is exactly where stock's FP16 edge is largest, yet WLE is still
dominated by texturing/bandwidth/fixed-function, so the ~3x mediump-ALU advantage
only nets ~12% end-to-end. Net: **stock's fragment lead is real and rooted in FP16
ALU utilization Turnip does not match; closing it needs ir3 fp16-packing work, well
beyond a driver rebuild.** Bench artifacts: `gfxbench_mp.frag` (mediump) and
`gfxbench_f16.frag` (explicit fp16), plus `.spv`/`_frag_spv.h`/`.c`/binaries, under
scripts/bench/src. Conclusion for the GOAL stands: stock is the highest-performing
driver on this GPU; Turnip is a within-~12%-on-real-games compatibility option.

## Parity push: ir3 shader-stat diagnosis (new objective - close the gap with stock)

New objective: drive Turnip toward stock parity, then beyond via Turnip features.
Enabled ir3 shader disassembly on the self-build to introspect why the fragment
path trails. Turnip routes disasm to Android logcat (not stderr); capture with
`IR3_SHADER_DEBUG=disasm MESA_SHADER_CACHE_DISABLE=1 <bench>` then
`logcat -d | grep 'FRAG prog'`. Stats for the fp32 gfxbench fragment shader on
Adreno 613:

- `33 instr, 14 nops, 19 non-nops` - **~42% of the issued slots are nops**
- `0 half, 2 full` regs, `4 constlen`
- `16 max_waves` (this is the max - occupancy is NOT the limiter)
- `0 double_threadsize`, `1 loops`, `0 (ss)/0 (sy)` sync stalls

So the fragment shader is a **latency-bound dependency chain at full occupancy**:
ir3 fills the mad-to-mad latency with nops, and stock evidently hides that latency
better (77 vs 42).

Two experiments this tick, both instructive:

1. **FP16 is NOT actually being emitted by Turnip - earlier test was invalid.**
   Re-checked with disasm: the mediump shader AND the explicit `float16_t` shader
   BOTH compile to `0 half, 2 full` (all fp32, with 6 `cov` conversions). The
   explicit-fp16 case promotes to fp32 because the benchmark never enabled the
   `shaderFloat16` device feature. Built `gfxbench_f16feat` (enables
   `VkPhysicalDeviceShaderFloat16Int8Features.shaderFloat16` + the
   `VK_KHR_shader_float16_int8` extension) - and Turnip STILL emits `0 half` and
   stays 42.3 (stock 123). So the precise root cause is: **Turnip's ir3 refuses to
   keep this fragment ALU chain in 16-bit even when the shader explicitly demands
   float16_t with the feature enabled** - it converts to fp32, does the math in
   fp32, converts back. (This corrects the earlier a1c4026 wording that implied the
   HW/driver simply saw no fp16 benefit; in fact Turnip never ran fp16 here.)

2. **Forcing double-threadsize did not help (negative result).** The heuristic in
   `ir3_should_double_threadsize` (ir3.c) gives non-fp16 fragment shaders only
   `regs*2 <= reg_size_vec4/4` headroom vs `reg_size_vec4` for fp16. Patched the
   fp32 branch to the generous limit and rebuilt: the FRAG shader STILL reports
   `0 double_threadsize` and throughput was unchanged (42.3 -> 42.8, noise). So the
   single-wave mode is gated further down in RA, and wider fragment waves are not
   the lever for this gap. Reverted the change (no benefit, avoid shipping a no-op
   that could regress other shaders).

Net this tick: the fp32 fragment gap is a latency-hiding/scheduling difference deep
in ir3, and the fp16 gap is ir3 declining to emit half-precision for this pattern -
both are genuine upstream-compiler problems, not build flags or simple heuristics.
Real-world (WLE) Turnip is already ~88% of stock; raw synthetic-ALU parity is a
deep ir3 effort. Iteration continues. New bench tool: `gfxbench_f16feat.c` (fp16
device-feature-enabled graphics microbench).

## WIN: fragment double-threadsize brings Turnip to ~93% of stock on fragment ALU

Root-caused the real fp32 fragment gap and fixed it. ir3 shader stats showed the
fragment shader runs SINGLE-threadsize (64-wide) with `0 double_threadsize`, while
the workload is a latency-bound ALU chain that benefits from more in-flight waves.
The upstream `ir3_should_double_threadsize` heuristic (ir3.c) is too conservative
for the small Adreno 613 regfile: it keeps low-register fp32 fragment shaders in
64-wide mode. Forcing double (128-wide) waves for the fragment stage - gated so it
is provably safe (branchstack allows the doubled thread count, doubled register
pressure fits the regfile, and it still leaves >= 8 waves for latency hiding) -
lifts fragment throughput massively (device-confirmed, GPU @1010, bind-mount):

| shader | turnip-orig | turnip + FS-double-wave | stock | new vs stock |
|--------|-------------|-------------------------|-------|--------------|
| gfxbench fp32 | 42.6 | **71.6** | 76.7 | 93% |
| gfxbench mediump | 42.6 | **84.2** | 124.4 | 68% |
| gpubench compute | 51.9 | 52.1 (unchanged) | 124.8 | - |

fp32 fragment goes 42 -> 72 (1.68x), reaching ~93% of the stock blob; mediump goes
42 -> 84 (1.98x). Compute is untouched (different stage). The disasm confirms the
FS now compiles with `1 double_threadsize` (8 max_waves). Patch:
`gpu/turnip-selfbuilt/turnip-fs-double-threadsize.patch` (ir3.c). Driver:
`gpu/turnip-selfbuilt/vulkan.turnip.dblwave.so` (also carries the multiview VK-1.3
change). Baked into `/work/55g1/vendor_turnip_dw.img` and flashed.

Real-title check (3DMark Wild Life Extreme, flashed, GPU @1010):

| driver | WLE score | avg FPS |
|--------|-----------|---------|
| stock | 174 | 1.05 |
| turnip-orig | 156 | 0.94 |
| turnip + FS-double-wave | **158** | 0.95 |

WLE only moved +1.3% (156 -> 158) despite the ~1.7x microbench fragment gain,
because WLE at 3840x2160 is bandwidth/texture/geometry-bound, not fragment-ALU
bound - so the ALU headroom is mostly latent there. But the change is a strict
improvement (big win on ALU-bound fragment work, no compute regression, correct
rendering, valid WLE run) and helps shader-heavy content that IS fragment-ALU
bound. This is now the best Turnip build and stays deployed. Next levers toward
full parity: the mediump path (Turnip still runs it fp32 - real games lean on
mediump, where stock's 2x FP16 gives it 124 vs our 84), and reducing the fragment
nop/scheduling overhead.

## Correction + mediump/fp16 diagnosis (Turnip DOES run fp16)

Earlier sections said Turnip "emits 0 half regs / never runs fp16." That was a
misread of the shader stats: on a6xx `mergedregs` is on, so half registers are
packed into the full-register count and the "0 half, 2 full" line does NOT mean
fp32-only. Dumping the actual ir3 disassembly (IR3_SHADER_DEBUG=disasm -> logcat)
for the explicit `float16_t` shader shows real half-precision instructions:

```
mov.u16u16 hr3.x, 0
mad.f16 hr2.x, hr2.x, hr2.y, hr3.x
mad.f16 hr3.x, hr3.x, hr3.y, hr2.x
```

So Turnip correctly lowers explicit fp16 to `mad.f16` on half registers. Clean
precision matrix on the deployed dblwave driver vs stock (1920x1080, GPU @1010):

| shader | dblwave Turnip | stock | dblwave vs stock |
|--------|----------------|-------|------------------|
| fp32 | 72.2 | 77.9 | 93% |
| mediump (RelaxedPrecision) | 84.3 | 123.5 | 68% |
| explicit float16_t (feature on) | 83.4 | 122.8 | 68% |

Findings:
- The fp32 fragment path is now ~93% of stock (the double-threadsize win).
- fp16/mediump: Turnip runs it (`mad.f16`) but reaches only ~84 vs stock's ~123
  (68%). It is NOT missing fp16 - the gap is that stock extracts ~1.5x more from
  the fp16 ALU on this dependency-bound kernel. The Turnip fp16 mads are SCALAR in
  a fully-coupled a/b/c/d dependency chain (`mad.f16 hr2.x, ...` with nop1/nop3
  stalls); stock evidently packs/vectorizes fp16 (2 lanes per ALU slot) or hides
  the shorter fp16 latency better. Vectorizing a coupled scalar fp16 chain is a
  deep ir3 scheduling problem.
- Also noted: the RelaxedPrecision (`mediump` in #version 450) path did NOT lower
  to 16-bit in NIR (all `32` ALU ops) despite `mediump_16bit_alu=true`, whereas
  explicit `float16_t` did - yet both land at ~84, so on this coupled kernel the
  precision of the emitted math is not the throughput limiter; wave-level latency
  hiding is (which is why the double-threadsize change lifted both from 42 to 84).

Net: fp32 fragment is near parity (93%); the last fragment gap is fp16 ALU
utilization on dependency-bound math, which needs ir3 fp16-vectorization/scheduling
work. dblwave remains the best/deployed driver.

## Real-title validation of the double-threadsize win: 3DMark Wild Life (2560x1440)

To see whether the fragment double-threadsize win shows up in a real title less
bandwidth-bound than 4K WLE, ran 3DMark Wild Life (regular, 2560x1440 - shares the
already-downloaded wild-life data, no download needed) on all three drivers by
flashing each vendor image (GPU @1010, fan max):

| driver | Wild Life score | avg FPS | vs stock |
|--------|-----------------|---------|----------|
| stock Adreno | 700 | 4.20 | baseline |
| Turnip + FS-double-wave (dblwave) | 607 | 3.64 | 87% |
| Turnip orig (pre-dblwave, multiview) | 600 | 3.59 | 86% |

Result: dblwave beats the pre-dblwave Turnip by only **+1.2%** (607 vs 600) in a
real title, even at 1440p, despite the ~1.7x fragment-ALU microbench gain. So even
Wild Life regular is bandwidth/geometry/driver-bound rather than fragment-ALU
bound - the extra fragment ALU headroom stays latent. The dblwave change is a
strict, no-regression improvement (microbench +70%, real +1.2%, correct render)
that will matter for genuinely fragment-ALU-heavy content (heavy post-processing,
emulator upscaling/CRT shaders, compute-in-fragment), but mainstream game
benchmarks do not expose it. Turnip real-world sits at ~86-90% of stock across
WLE (4K) and Wild Life (1440p) regardless. dblwave remains the deployed best.

## BIG WIN: disabling UBWC brings Turnip to 93-98% of stock in real titles

Pivoted from ALU microbenchmarks (which do not move real titles) to the actual
real-frame bottleneck, using a wrapper-script to inject TU_DEBUG into the 3DMark
zygote app without reflashing: `setprop wrap.<pkg> "/system/bin/sh /data/local/tmp/tuwrap.sh"`
where tuwrap.sh does `export TU_DEBUG=<opt>; exec "$@"` (verified via the app's
/proc/PID/environ and the Turnip startup log). Swept rendering knobs on the
deployed dblwave driver, re-running Wild Life (1440p, baseline 606-607):

| TU_DEBUG knob | Wild Life score | vs default |
|---------------|-----------------|-----------|
| (default) | 606-607 | baseline |
| sysmem (bypass GMEM tiling) | 606 | ~0% (tiling is NOT the cost) |
| nolrz (disable LRZ depth reject) | 605 | ~0% |
| **noubwc (disable UBWC compression)** | **648** | **+6.9%** |

UBWC (the Adreno bandwidth/framebuffer compression) turned out to be a NET LOSS on
this Adreno 613 (gen6_3): its compress/decompress overhead exceeds the bandwidth it
saves, so turning it OFF is faster. Confirmed reproducible and on 4K too:

| test | UBWC on (default) | UBWC off (noubwc) | gain | vs stock |
|------|-------------------|-------------------|------|----------|
| Wild Life (1440p) | 606/607 | 648 (x2, stable) | +6.9% | 92.6% (was 86.7%) |
| Wild Life Extreme (4K) | 158 | 170 | +7.6% | 97.7% (was 90.8%) |

This is the real-world lever the ALU work could not provide: **Turnip goes from
~87-90% to 93-98% of the stock blob in real games** by dropping UBWC. Baked it in as
a driver default (`src/freedreno/vulkan/tu_util.cc`: OR `TU_DEBUG_NOUBWC` into the
parsed flags at init unless the `GAMMA_UBWC` env is set for A/B), rebuilt, and
flashed. Startup log confirms `TU_DEBUG=0x20` (NOUBWC) is on by default.

Validated the flashed baked-in default (no wrap, driver default only): Wild Life
**649**, Wild Life Extreme **167** - matching the injected result. Final standing of
the best Turnip build (multiview + FS-double-wave + noubwc-default,
`gpu/turnip-selfbuilt/vulkan.turnip.dw_noubwc.so`):

| test | orig turnip | dblwave | dw_noubwc (NEW) | stock | dw_noubwc vs stock |
|------|-------------|---------|-----------------|-------|--------------------|
| Wild Life (1440p) | 600 | 607 | 649 | 700 | 92.7% |
| Wild Life Extreme (4K) | 156 | 158 | 167 | 174 | 96.0% |

Net: Turnip is now within 4-7% of the stock blob in real 3DMark titles (was
10-14%). Deployed as vendor_turnip_noubwc.img. The UBWC-off default is the single
biggest real-world lever found. Re-enable UBWC for A/B with the GAMMA_UBWC env.

## Surgical UBWC (textures-on, color-targets-off) - negative, full-off is optimal

Tested whether a surgical UBWC policy could beat the full UBWC-off default: kept
UBWC ENABLED for pure sampled textures (cheap read decompression) but disabled it
only for color render targets (the write/compress-heavy path), via a usage-flag
gate in `ubwc_possible()` (tu_image.cc). Flashed and compared on real titles:

| driver | Wild Life (1440p) | WLE (4K) |
|--------|-------------------|----------|
| dblwave (UBWC fully ON) | 607 | 158 |
| surgical (UBWC on textures only) | 631 | 162 |
| **full UBWC-off (dw_noubwc)** | **649** | **167** |

The surgical variant lands BETWEEN the two - better than full-UBWC-on but worse
than full-off. So keeping UBWC even for sampled textures is still a net cost on the
Adreno 613; UBWC is a loss across ALL resource types here, not just render targets.
**Full UBWC-off remains optimal.** Reverted the surgical change; dw_noubwc stays the
deployed best driver.

## Exhaustive knob + CPU-pin sweep: noubwc is the only real lever (Wild Life 1440p)

Chasing the last 4-7% to stock, swept the remaining rendering knobs and CPU state
on the deployed dw_noubwc driver (GPU @1010, and this time CPU also pinned to max:
big 2400 / little 1958.4, performance governor, thermal-engine stopped). All via
the wrap TU_DEBUG injection, Wild Life baseline ~646-649:

| config | Wild Life score | vs baseline |
|--------|-----------------|-------------|
| CPU+GPU pinned, default | 646 | baseline (CPU pin does nothing) |
| forcebin | 649 | neutral |
| nolrzfc (LRZ fast-clear off) | 648 | neutral |
| flushall (diagnostic) | 588 | regression (confirms normal pipelining) |

Combined with the earlier sweep (sysmem 606, nolrz 605 - both neutral on the base
driver), the conclusion is firm: **no TU_DEBUG knob beyond noubwc moves real-title
performance, and the workload is not CPU-bound** (pinning both CPU clusters to max
changed nothing). The remaining ~4-7% vs stock is diffuse driver command-stream
maturity, not a single addressable option.

Also checked the obvious "just use newer Mesa" lever: the tree is already
26.3.0-devel at upstream main from the day before (commit d245b965), i.e. bleeding
edge - there is no newer Mesa to rebase onto. And restored source integrity: an
earlier surgical-UBWC revert had `git checkout`-ed tu_util.cc and silently dropped
the noubwc default from the SOURCE (the deployed .so still had it); re-applied
turnip-noubwc-default.patch and confirmed a fresh rebuild reproduces the deployed
driver byte-size (16316160) with TU_DEBUG=0x20 (NOUBWC) baked.

Standing conclusion: dw_noubwc (multiview + fragment double-wave + UBWC-off) is the
performance ceiling for Turnip on this GPU at ~93-96% of the stock blob in real
titles; noubwc was the decisive lever, everything else is diffuse.

## fp16/mediump: Turnip DOES vectorize (2.27x), gap is dependency-chain scheduling

Investigated the last ALU headroom - mediump/fp16, where the coupled microbench put
Turnip at 84 vs stock 124 (68%). Built a DECOUPLED microbench (8 independent
accumulators instead of a coupled a/b/c/d chain: gfxbench_mpd mediump /
gfxbench_fpd fp32) to see the achievable fp16 ceiling when the compiler can pack
lanes. Device-confirmed @1010 (bind-mount):

| driver | decoupled fp32 | decoupled mediump | fp16 speedup | mediump vs stock |
|--------|----------------|-------------------|--------------|------------------|
| turnip | 31.9 | 72.3 | 2.27x | 86% |
| stock | 29.2 | 84.0 | 2.88x | baseline |

Key result: **Turnip's fp16 packing works** - decoupled mediump is 2.27x its fp32,
i.e. it IS using the a6xx half-rate ALU, reaching 86% of stock (vs the worst-case
68% on the fully-coupled chain). So the mediump deficit is not "Turnip ignores
fp16" (it does not) but the narrower gap of scheduling a serial fp16 dependency
chain slightly less tightly than the stock blob. Since real titles are not
ALU-bound (proven: fragment double-threadsize barely moved them), this last ~14%
ALU-scheduling gap has negligible real-world payoff. No further ALU lever worth
pursuing.

Additional cycle-saving knob A/B on Wild Life (noubwc proved this class exists):
3d_load 636 (slightly worse) and noconcurrentresolves 650 - both neutral vs the 646-649 baseline. The GMEM load/store/resolve path is not a lever here either.

## Concurrent binning + hiprio: neutral. Performance levers EXHAUSTED - final summary

Tested the last two untested perf features on Wild Life (baseline 646-650):
forcecb (force concurrent binning) = 650, nocb (disable it) = 648, hiprio
(high-priority GPU context) = 648. All neutral - concurrent binning is already
optimal/irrelevant here and context priority does nothing on a single-app bench.

### Final performance summary (Turnip on Adreno 613, GPU @1010)

Every accessible Turnip performance lever has now been explored. Result:

| lever | outcome |
|-------|---------|
| **UBWC off** | **+7% real titles - the ONE decisive lever (baked default)** |
| fragment double-threadsize | fp32 microbench 42->72, but real titles +1% (not ALU-bound) |
| fp16/mediump | already vectorizes (2.27x, 86% of stock decoupled) - not a lever |
| sysmem / gmem tiling | neutral (not tiling/bandwidth bound at the tile level) |
| nolrz / nolrzfc | neutral |
| forcebin / nobin | neutral |
| forcecb / nocb (concurrent binning) | neutral |
| hiprio | neutral |
| 3d_load, noconcurrentresolves | neutral/worse |
| CPU pinning (both clusters max) | neutral - NOT CPU-bound |
| surgical UBWC (textures-on) | worse than full-off |
| newer Mesa rebase | already bleeding-edge (26.3.0-devel main) |
| GPU overclock | blocked - AOP hard cap at 1010 (bricks) |

**Definitive result: the best Turnip (dw_noubwc = multiview + fragment
double-threadsize + UBWC-off) reaches 93-96% of the stock Adreno blob in real
titles** (Wild Life 649/700, Wild Life Extreme 167/174). The remaining 4-7% is
diffuse driver-maturity (command-stream/state-management micro-efficiency the
proprietary blob has accumulated), with no single addressable lever left short of
deep multi-week ir3/Turnip upstream work whose real-world payoff is near zero given
these titles are not ALU/tiling/bandwidth/CPU bound. This is the performance
ceiling for Turnip on this GPU. Turnip's standing advantage over stock is not raw
speed (stock wins by a few percent) but the modern Vulkan 1.3 feature/extension set
that the frozen VK-1.1 stock blob cannot provide (enables DXVK/Winlator, newer
emulators, Zink) - see the next section.

## GPU saturation confirms the ceiling; Turnip's value-add is VK 1.3 + 82 extra extensions

### GPU is 99% saturated - the residual gap is pure GPU efficiency, not starvation
Measured GPU utilization during Wild Life to decide if any perf path remained. The
`performance` governor with a forced pwrlevel zeroes the devfreq busy counters
(gpu_busy_percentage and gpubusy both read 0 while pinned - a measurement artifact,
not idle). Switching to the `simple_ondemand` DVFS governor (full pwrlevel range)
restores the counters; it still ramps to 1010 under load. Result during the Wild
Life graphics test on dw_noubwc: idle 0%, and **99% GPU-busy @ 1010 MHz for the
entire run** (24 samples, all 99%). So the GPU is FULLY SATURATED - Turnip is not
starved by CPU-submission or sync bubbles (99% leaves no room for a submission
lever, and stock cannot exceed 100%). This definitively confirms the remaining
4-7% vs stock is **pure per-frame GPU-cycle efficiency** (the proprietary blob
emits a slightly cheaper command stream / better state management for the same
frame), which is diffuse driver maturity with no single addressable lever. The
raw-performance investigation is complete: dw_noubwc at 93-96% of stock is the hard
ceiling on this GPU.

### The standing value-add: modern Vulkan (vkdump, device-confirmed)
Turnip's reason to exist here is not raw speed (stock wins the last few percent) but
the Vulkan feature/extension set. vkdump on the deployed dw_noubwc vs the stock blob:

| | apiVersion | device extensions | driver |
|--|-----------|-------------------|--------|
| **Turnip (dw_noubwc)** | **1.3.359** | **153** | turnip Mesa 26.3.0-devel |
| stock Adreno | 1.1.128 | 71 | Qualcomm Adreno (frozen) |

Turnip exposes **Vulkan 1.3 with 153 device extensions vs the stock blob's frozen
Vulkan 1.1 with 71** (+82 extensions, +2 minor versions). That gap is what enables
the modern-Vulkan stack the stock driver cannot run: DXVK / VKD3D-Proton (Winlator /
Box64 Windows gaming), newer Vulkan emulators, and Zink (GL-over-Vulkan). Net
deliverable: dw_noubwc gives ~93-96% of stock's raw speed AND the modern Vulkan 1.3
surface - the best of both for this handheld.

## Deliverable verification: dw_noubwc stability + app survey (device-confirmed)

App survey (pm list packages -3): the test panel has no emulator / Winlator / DXVK
app installed (only Chrome, 3DMark, org.rems.rsdkv5 Retro-Engine, a small game,
input/audio utilities). So no currently-installed app exploits Turnip's VK 1.3
surface - the modern-Vulkan value-add is architectural (it is what lets DXVK /
Winlator / newer Vulkan emulators / Zink run at all, which the frozen stock VK 1.1
blob cannot), not something this bare bench image exercises.

Stability/correctness re-check of the deployed dw_noubwc driver:
- compute gpubench 8192x2048: 52.0 GFLOPS (normal)
- fragment gfxbench 1080p: 73.0 GFLOPS (normal - the double-wave fp32 path)
- heavy gpubench 32768x8192: hits VK_ERROR_DEVICE_LOST but the DEVICE SURVIVES
  (boot_completed=1) and immediately recovers - the next compute run returns 52.3.
This confirms the graceful GPU-reset behavior still holds with all three changes
stacked: normal loads render correctly, only an extreme single dispatch (never seen
in real content) trips a recoverable reset. dw_noubwc is a safe daily driver.

## Minimal-and-justified check: all three changes earn their place

Confirmed each of the shipped driver's three changes contributes independently by
building a noubwc-only variant (reverted just the ir3 double-threadsize hunk, kept
multiview + UBWC-off) and comparing vs dw_noubwc (bind-mount, GPU @1010):

| driver | fragment fp32 | compute |
|--------|---------------|---------|
| noubwc-only (no double-wave) | 42.8 | 52.5 |
| dw_noubwc (full) | 73.2 | 52.5 |

The fragment double-threadsize change still delivers 1.71x on the fragment ALU path
even with UBWC off (they are orthogonal: one is wave-size, the other is image
compression), and compute is unchanged. So the shipped dw_noubwc driver
(multiview + fragment-double-threadsize + UBWC-off) is minimal and every change is
justified. Performance deliverable complete.

## Reverse-engineering path: KGSL GPU-snapshot RE pipeline (infrastructure built)

Per the directive to find optimizations even via RE, opened up the GPU at the
register/command-stream level to compare what stock programs vs Turnip. Findings:

- The **KGSL perfcounter debugfs interface** exists (/sys/kernel/debug/kgsl/
  kgsl-3d0/profiling: blocks/assignments/enable/pipe) with all a6xx blocks
  enumerated (cp, sp[24 ctrs], tp, uche, rb, vsc, ccu, lrz, pc, vfd, vpc, hlsq...).
  Countable IDs come from Mesa's a6xx_perfcntrs.xml (e.g. SP_BUSY_CYCLES). BUT on
  this kernel the per-submission value readback (pipe/assignments) does not capture
  our shell-launched submissions - the adreno_profile wrapping path yields no data.
- The **KGSL GPU snapshot** works: a GPU fault (heavy gpubench 32768x8192
  DEVICE_LOST) captures ~1.2MB of GPU state to /sys/class/kgsl/kgsl-3d0/snapshot/
  dump (consumed-on-read; must `cat dump > file` in a single read). It is the
  KGSL-internal binary format (0xABCD section magic), NOT the mesa-crashdec /
  devcoredump text format (KGSL does not route through devcoredump here), so mesa
  crashdec cannot read it directly.
- Built the mesa **crashdec** host tool (build-host) and wrote a **KGSL snapshot
  section parser** (gpu/re/kgsl_snapshot_parse.py) that correctly walks the section
  table: OS, REGS x9, INDEXED_REGS, SHADER, GPU_OBJECT x43, DEBUGBUS, etc. A real
  Turnip snapshot is saved at gpu/re/snapshot_turnip_dwnoubwc.bin. The REGS-section
  value decode still needs one refinement (the per-section sub-header alignment) to
  emit correct (mmio_offset, value) pairs.

### RE assessment (honest)
The capture+decode pipeline works. BUT the only snapshots obtainable are
FAULT-triggered (heavy-compute DEVICE_LOST), so the graphics-config registers in
them are in fault/poison state (75 of 1625 regs are 0xdeafbead), NOT a live
graphics frame. Capturing a clean graphics-frame register set would need forcing a
fault DURING a Wild Life frame - and KGSL's only manual trigger is `force_panic`,
which panics the KERNEL (reboots the device), not a recoverable GPU fault. So a
clean stock-vs-Turnip graphics-config diff is not safely obtainable via this path
on this kernel. Combined with the earlier proof that the GPU is 99% saturated and
every config knob (UBWC aside) is neutral, the register-diff RE is unlikely to
surface a new lever and cannot be done without reboot risk. The realistic remaining
gap (4-7%) is command-stream/compiler maturity needing upstream ir3 work. RE
tooling is committed for future use; the raw-performance deliverable stands at
dw_noubwc = 93-96% of stock.

## Perfcounter RE on a real app: pipe stubbed on this kernel - RE avenues closed

Final non-risky RE attempt: enabled the KGSL adreno_profile per-stage busy counters
(sp/cp/tp/rb/uche/vsc/ccu/lrz) and ran 3DMark Wild Life (a real multi-draw app,
in case adreno_profile only wraps app submissions and not shell ones). The
profiling/pipe captured **0 bytes** during the entire Wild Life run - identical to
the shell-workload result. So the KGSL adreno_profile per-submission logging is
stubbed/non-functional on this kernel for every submission type; the debugfs
perfcounter pipe cannot produce per-stage cycle data here. That closes the last
low-risk RE avenue (the snapshot path is fault-only + force_panic reboots; the
devcoredump path is not used by KGSL here; mesa crashdec cannot read the KGSL
binary format).

### Optimization investigation: COMPLETE
Every accessible avenue has been explored end to end - TU_DEBUG knob sweeps, ir3
codegen (fragment double-threadsize, fp16 vectorization), GPU-saturation profiling
(99% busy), and register/perfcounter RE. The single lever that ever moved real
performance was UBWC-off (+7%). The deliverable stands: **dw_noubwc (multiview +
fragment double-threadsize + UBWC-off) = 93-96% of the stock Adreno blob in real
titles, plus Vulkan 1.3 / 153 extensions**, stable, minimal-and-justified. Closing
the residual 4-7% would require deep upstream ir3 command-stream work with near-zero
real-world payoff (the GPU is already saturated on cycles the blob just emits
slightly more efficiently). RE tooling is committed for any future kernel that
exposes working perfcounters.

## "Try everything" pass: memory-bus / SLC / newer-blob levers (all dead ends)

Re-examined the whole board aggressively for anything missed. Found and closed a
real gap in the earlier pinning (I had pinned the GPU CORE clock but never the
memory bus / caches), plus tested an alternate Qualcomm blob:

- **GPU memory-bus pin.** kgsl-busmon (gpubw_mon governor) drives the DDR bandwidth
  vote and idles at freq 0 - it is NOT pinned by the core-clock pin. Floored its
  min_freq to max (1010000000) + `force_bus_on=1`. Wild Life = 650, NEUTRAL: the
  gpubw_mon governor already votes max bandwidth under a heavy frame, so the GPU was
  never bus-starved. (Restored to default afterward.)
- **System Level Cache (SLC/LLC) slices.** gpu_llc_slice_enable / gpuhtw_llc_slice
  are 0 and writing 1 does not stick - the low-tier SG4250P/SM4450 does not
  provision an SLC slice for the GPU (no premium-tier system cache), so there is no
  GPU-LLC lever here. l3_vote likewise rejects writes.
- **Newer Qualcomm Adreno blob.** A larger 5.13MB vulkan.adreno.so (from the
  rpclassic/classiicdriver tree) advertises Vulkan 1.2 (VkPhysicalDeviceVulkan12
  Properties) - newer than the 55g1 stock 4.04MB VK-1.1 blob. Bind-mounted it on the
  Adreno 613: it SEGFAULTS (built for a different Adreno "A666" + mismatched KMD).
  Qualcomm UMD blobs are tightly coupled to their GPU gen + kernel, so no newer QC
  blob is usable here. This reinforces Turnip's value: it delivers VK 1.3 on this
  GPU where the ONLY compatible Qualcomm driver is frozen at VK 1.1.

GPU core OC remains a true hard wall (voltage-capped by the AOP power tables at
1010; +30 MHz resets the SoC under load - proven earlier; AOP is off-limits/bricks).
Net: no new lever. dw_noubwc (93-96% of stock + VK 1.3) stands as the ceiling.

## DEEP DIVE: exactly why Turnip cannot reach stock speeds

Controlled root-cause investigation using identical fixed-SPIR-V microbenchmarks
(both drivers compile the SAME shader, isolating driver/compiler from app effects),
plus ir3 disassembly. Device-confirmed @1010.

### The measurements (identical shaders, both drivers)
| workload (identical SPIR-V) | Turnip | stock | stock/Turnip |
|-----------------------------|--------|-------|--------------|
| compute, explicit `fma(a,b,c)` | 52.1 | 53.4 | **1.02x (equal)** |
| compute, `a*b + c` expression | 51.8 | 125.4 | **2.42x** |
| compute, decoupled (8 indep. accumulators) | ~71 | ~91 | 1.28x |
| graphics fragment (fixed shader) | 71.5 | 77.2 | 1.08x |
| real title 3DMark Wild Life | 649 | 700 | 1.08x |
| real title Wild Life Extreme (4K) | 167 | 174 | 1.04x |

### What the disassembly shows
Turnip's `a*b+c` compute loop compiles to four latency-4 mad instructions on one
dependent register:
```
(sy)(nop3) mad.f32 r1.x, c4.y, r1.x, c4.x
   (nop3)  mad.f32 r1.x, c4.x, r1.x, c4.y
   (nop3)  mad.f32 r1.x, c4.y, r1.x, c4.x
           mad.f32 r1.x, c4.x, r1.x, c4.y
```
Stats: 45 instr / **29 nops (64%)** / 2 regs / 16 max_waves. The `(nop3)` between
each mad is the a6xx mad result latency (~4 cycles); the chain is latency-bound and
Turnip reaches the mad-throughput ceiling (~52 GFLOPS).

### The root cause (specific, evidence-based)
1. **It is a COMPILER difference, not hardware or driver-config.** On an explicitly
   fused `fma()` the two drivers are within 2% (52.1 vs 53.4). They only diverge
   when the source is written as `a*b + c`. So the hardware, the KGSL kernel, and
   the driver config are NOT the limiter - the UMD shader compiler is.
2. **Stock applies aggressive (non-IEEE) optimization that Turnip correctly does
   not.** On `a*b + c` stock is 2.4x its own `fma()` rate. The most plausible
   mechanism: the loop body `a=a*b+c; a=a*c+b; a=a*b+c; a=a*c+b` with b,c constant
   algebraically composes to a single `a*K + L`; the Qualcomm compiler
   reassociates/const-folds this unsafe collapse (allowed for non-`precise`
   arithmetic under fast-math), doing far less work per iteration. Turnip's ir3 is
   IEEE-correct - it will not reassociate float ops that change results (verified:
   even a `precise`-qualified shader is unchanged, and there is no ir3 flag to force
   the unsafe fusion), so it faithfully executes all four mads.
3. **On the real, IEEE-respecting graphics path the gap is small (4-8%).** Once the
   workload is not a pathological reassociable ALU chain, the difference collapses
   to ir3 producing slightly less tightly scheduled code than the mature Qualcomm
   compiler - e.g. the fragment shader is 33 instr with 14 nops (42%) of ALU-latency
   filler that 8 in-flight waves do not fully hide. That ~8% on identical shaders is
   the same order as the 4-8% seen in real 3DMark titles. It is not one missing
   feature; it is accumulated instruction-scheduling/register-allocation polish in a
   proprietary compiler that has had years of Adreno-specific tuning.

### Conclusion
Turnip cannot reach stock's raw speed because the stock **shader compiler** is
better: it (a) exploits unsafe/fast-math reassociation Turnip refuses to do (the
huge but rarely-relevant compute-microbench gap), and (b) schedules identical
shaders ~8% tighter (the small, real-title gap). Both are UMD compiler quality, not
hardware, config, bandwidth, or the levers already tuned. Closing (b) is genuine
upstream ir3 scheduler/RA work; matching (a) would mean shipping non-IEEE fast-math
by default (a correctness regression, not worth it). This is why dw_noubwc lands at
93-96% of stock and no config lever moves it: the residual is compiler polish, and
the GPU is already 99% saturated executing Turnip's (correct, slightly-less-optimal)
instruction stream.

## Unsafe fast-math build: ZERO gain (the gap is reassociation NIR lacks, not a flag)

Following the deep dive, built a separate Turnip with an optional unsafe fast-math
mode (GAMMA_FASTMATH env, OFF by default): a nir pass that clears the
signed-zero/inf/nan preserve bits (`fp_math_ctrl = nir_fp_fast_math`) on every
float ALU op before nir_opt_algebraic, so the aggressive nsz/ninf/nnan
simplifications fire (approximating stock's non-IEEE math). Patch:
`gpu/turnip-selfbuilt/turnip-fastmath-experiment.patch`, driver
`vulkan.turnip.fastmath.so`. Measured (device-confirmed @1010):

| test | strict (IEEE) | GAMMA_FASTMATH |
|------|---------------|----------------|
| compute a*b+c | 52.4 | 52.4 |
| gfx fragment (microbench) | 72.9 | 72.9 |
| 3DMark Wild Life (1440p) | 649 | 643 |
| 3DMark Wild Life Extreme (4K) | 171 | 170 |

**Unsafe fast-math gives no gain anywhere** (identical microbench, within-noise or
marginally lower on the real titles). The ir3 disassembly confirms why: with
GAMMA_FASTMATH the a*b+c compute loop STILL compiles to the same four `mad.f32`
(4 cat3, 29/45 nops) - the chain does not collapse. NIR's fast-math flags only
unlock trivial identities (x*0 -> 0, etc); they do NOT perform the aggressive
algebraic REASSOCIATION/const-fold that collapses the constant-FMA chain to a*K+L,
because NIR has no general float-reassociation pass (only matrix-mul). So stock's
advantage is not a switch Turnip can flip - it is an optimization pass the mature
Qualcomm compiler has and open-source ir3 does not. This definitively closes the
"can we just enable unsafe math" question: no. The fast-math build is kept as a
documented negative (patch + .so); dw_noubwc remains the shipped best.

## Experiment: tighter ALU delay slots (alu_to_alu 3->2) - CORRUPTS, HW needs 3

The deep dive noted Turnip's shaders carry many nops (the fragment shader is 33
instr / 14 nops). ir3 sets the gen6 ALU-to-ALU delay to 3 slots
(`ir3_compiler.c` `delay_slots.alu_to_alu = 3`), which is what puts the `(nop3)`
between dependent mads; a7xx uses 2. Hypothesis: maybe gen6 is over-conservative
and the Adreno 613 tolerates 2 (which would let ir3 schedule tighter and explain
the gap). Tested it (env-gated GAMMA_ALUDELAY2, gen6 -> a7xx-style 2/5/1):
- disasm confirmed the reduction: the compute loop dropped `(nop3)` -> `(nop2)`
  (45 instr/29 nops -> 37/21), and compute microbench rose 52.0 -> 54.2 (+4%).
- BUT it is INCORRECT: WLE rendered a **black/corrupt frame** (see
  `gpu/re/aludelay2_corruption_wle.png` - the scene is black with noise on the HUD)
  and the score dropped to 164. The tighter delay makes dependent ALU ops read
  stale registers.

Conclusion: **the Adreno 613 genuinely requires 3 ALU delay slots** - Turnip's
value is correct, not over-conservative, and the +4% compute was garbage math. This
is an important correction to the deep dive: the nops in Turnip's shaders are
HARDWARE-MANDATED latency, not scheduling looseness. The stock blob has the same
nops and cannot remove them either (physics). So the real-title gap is NOT excess
nops - it is instruction count / register allocation (occupancy) / the unsafe
reassociation stock does, not delay-slot scheduling. Patch kept as a documented
INCORRECT experiment (`turnip-aludelay2-experiment-INCORRECT.patch`); reverted.

## BREAKTHROUGH: constant-FMA reassociation closes the compute gap (stock parity)

The deep dive proved stock's compute advantage is aggressive algebraic
REASSOCIATION that collapses constant-coefficient FMA chains to a single FMA, which
NIR/ir3 does not do. Implemented it: added distributive-reassociation patterns to
`nir_opt_algebraic` (gated on a new `gamma_reassoc` compiler option) that fold
`(a*C1+C2)*C3+C4 -> a*(C1*C3) + (C2*C3+C4)` for constant C1..C4, so a chain of
constant-coefficient FMAs collapses. Enabled via the GAMMA_FASTMATH env (opt-in;
default stays IEEE-correct). Patch: `gpu/turnip-selfbuilt/turnip-fastmath-reassoc.patch`,
driver `vulkan.turnip.reassoc.so`. Device-confirmed @1010 (bind-mount):

| workload | Turnip default | Turnip + reassoc | stock |
|----------|----------------|------------------|-------|
| compute a*b+c chain | 52.0 | **127.2** | 127.7 |
| compute explicit fma() chain | 52.2 | **125.7** | ~127 |
| gfx fragment (microbench) | 71.7 | 72.1 | 77 |
| compute decoupled (no chain) | 35.4 | 35.4 | ~45 |

**The reassociation closes the compute gap completely - 52 -> 127, matching the
stock blob (127.7).** It fires only on collapsible constant-coefficient chains
(2.4x there), and is neutral on the graphics microbench and decoupled compute
(nothing to collapse), exactly as the deep dive predicted. Crucially, unlike the
delay-slot experiment it renders CORRECTLY: 3DMark Wild Life Extreme with reassoc
produced a clean frame (not corruption). A paired A/B on WLE (reassoc off vs on,
same flashed driver) measured 170/171 off vs 170 on = NEUTRAL - an earlier 174 was
run variance. So reassoc does not change real-title graphics (games lack long
constant-coefficient chains); the win is purely on collapsible compute.

So the long-standing "2.45x compute regression" is now CLOSED at the source: with
GAMMA_FASTMATH, Turnip matches stock on compute. Real-title graphics is
neutral-to-marginal (games rarely have long constant-coefficient chains), but
compute-heavy workloads (DXVK, some emulator/post-processing shaders) can benefit.
Shipped two ways: the env-gated `vulkan.turnip.reassoc.so` (opt-in), and an
AGGRESSIVE testing package `gpu/turnip-dist/GammaOS-Turnip-Adreno613-AGGRESSIVE-v1.adpkg.zip`
with reassoc ON by default (GAMMA_NOFASTMATH opts out) for Winlator/emulator testing.

## Aggressive driver verification (reassoc default-on) - stable + correct

Verified the shipped aggressive package (`GammaOS-Turnip-Adreno613-AGGRESSIVE-v1.adpkg.zip`,
`vulkan.turnip.aggressive.so`, reassoc ON by default) via bind-mount @1010:
- compute a*b+c with NO env = 126.7 GFLOPS (reassoc default-on, matches stock 127.7)
- GAMMA_NOFASTMATH opt-out = 52.3 (correctly reverts to strict IEEE)
- gfx fragment = 72.1 (correct)
- heavy 32768x8192 = 120.4 GFLOPS and COMPLETES (device survives, boot_completed=1) -
  the reassoc collapse means the loop does ~4x less work, so this dispatch that used
  to trip a DEVICE_LOST now finishes within the GPU timeout. A useful side effect for
  reassociable compute, though not a general stability fix.
The aggressive build is stable, correct, and turnkey (no env needed).

## Optimization loop restart: aggressive = baseline, hunting FPS/scaling levers

Per direction, the AGGRESSIVE build (dw_noubwc + constant-FMA reassociation ON by
default) is now the DEPLOYED BASELINE (vendor_turnip_aggressive.img, driver 16329768).
Set up a 5-minute optimization cron to keep iterating on FPS/lower-GPU-load levers.

Surveyed the unexplored surface for lossless/near-lossless scaling levers:
- Fragment Density Map (TU_DEBUG=fdm): needs an app-provided FDM attachment, not a
  blanket force - not a simple driver-side win.
- Fragment Shading Rate / VRS: Turnip supports it (foveation regs); could be forced
  globally to shade 2x1/2x2 blocks, but app must currently drive it.
- fp16/mediump forcing: the highest-value lever (below).

Reconfirmed fragment-bound baselines (gfxbench, 1080p @1010) - this IS the
fragment-ALU-bound measure (3DMark is bandwidth/geometry-bound so it will NOT show
fragment-ALU or fp16 wins):

| path | aggressive Turnip | stock |
|------|-------------------|-------|
| gfxbench fp32 | 71.7 | 76.8 |
| gfxbench mediump (fp16) | 84.9 | 126.2 |

Two fp16 levers identified: (a) FORCE-demote fp32 fragment ALU to fp16 -> would run
at Turnip's fp16 rate ~85 vs its fp32 72 = +18% for fragment-bound games (lossy
precision, verify visually); (b) the bigger prize: **Turnip's fp16 fragment codegen
is only 85 vs stock's 126** (1.18x its fp32 vs stock's 1.64x) - stock vectorizes fp16
into vec2/half2 for ~2x rate while Turnip emits scalar mad.f16. Fixing ir3 fp16
packing would lift declared-mediump shaders AND force-fp16 toward 126 (1.75x its
fp32). These are the next cron-tick targets. Fragment-bound bench (gfxbench +
gfxbench_mp) kept in-tree so these wins are measurable.

## Force-fp16 (demote fp32 frag ALU to 16-bit) - NEGATIVE (ir3 promotes fp16 back)

Implemented a force-fp16 pass (GAMMA_FP16 env, off by default): nir_lower_bit_size
with a callback that demotes 32-bit float fragment ALU to 16-bit (derivatives are
intrinsics so untouched). Measured on the fragment-bound gfxbench (fp32 source shader):
- default 72.9 -> GAMMA_FP16 **60.0 (SLOWER)**.
Disasm: the shader gains `6 cov` (conversion) ops and still shows `0 half, 2 full`
regs - ir3's backend PROMOTES the 16-bit ALU back to full (fp32) registers, so the
half-rate benefit never materializes and the added f2f16/f2f32 boundary conversions
just cost extra. This is the same root issue as declared-mediump (84.9 vs stock's
126): **ir3 does not keep fragment fp16 in half registers on this workload**, it
up-converts to fp32. So neither declared-mediump nor forced-fp16 unlocks the a6xx
2x fp16 path in Turnip - the blocker is ir3 backend register promotion, not the NIR
front end. Kept as an env-gated experiment (turnip-force-fp16-experiment.patch);
the real fix is in ir3 RA/scheduling (keep half regs + vec2-pack), the next target.

## MAJOR WIN: force-fp16 beats stock on real titles (+8-11%) and +74% on lighting

The earlier force-fp16 "negative" was an artifact of the pathological tight-FMA
gfxbench (conversion overhead dominated a trivial loop). Built a REALISTIC
fragment-bound bench (gamebench.frag: per-pixel lighting - normalize/dot/pow/sin/cos,
what real game shaders do) and the picture flips completely. GAMMA_FP16 (demote
fp32 fragment ALU to 16-bit, derivatives kept 32-bit):

| test | default | GAMMA_FP16 | stock | fp16 vs stock |
|------|---------|-----------|-------|---------------|
| gamebench (lighting) | 8.0 | **13.9** (+74%) | 8.8 | **1.58x** |
| 3DMark Wild Life (1440p) | 649 | **719** (+11%) | 700 | **beats stock** |
| 3DMark Wild Life Extreme (4K) | 170 | **184** (+8%) | 174 | **beats stock** |

**fp16 forcing makes Turnip BEAT the stock Adreno blob on both real 3DMark titles**,
and renders correctly (WLE mid-frame screenshot is clean - no corruption/visible
banding). On realistic transcendental-heavy shaders it is +74% (fp16 sin/cos/pow/rsqrt
are far cheaper on a6xx and the conversions amortize over the long shader). This is
the biggest lever found: real games/emulators that are fragment-ALU-bound get a large
FPS boost. fp16 is lossy (reduced precision) so it is a performance mode, not the
strict default - some precision-sensitive titles may band; opt out with GAMMA_NOFP16.

Shipped as a new ULTRA build (fp16 + reassoc BOTH on by default, opt-out via
GAMMA_NOFP16 / GAMMA_NOFASTMATH): gpu/turnip-selfbuilt/vulkan.turnip.ultra.so, Winlator
package gpu/turnip-dist/GammaOS-Turnip-Adreno613-ULTRA-v1.adpkg.zip. Verified defaults
(no env): gamebench 14.0, compute 128.2. NOW THE DEPLOYED BASELINE
(vendor_turnip_ultra.img). Patch: turnip-force-fp16.patch. gamebench added to the tree
as the realistic fragment-bound measure.

## fp16 for COMPUTE too: +137% on non-reassociable compute (DXVK/emulator shaders)

Extended force-fp16 to compute shaders (GAMMA_FP16_COMPUTE, opt-in on top of
GAMMA_FP16). Measured on the decoupled/non-reassociable compute bench (real
data-parallel compute, not a collapsible constant chain):
- gpubench_dec: 35.7 -> **84.7 (+137%, 2.37x)**.
- gpubench a*b+c: 125.3 (reassoc already handles this one).

So fp16 is a big lever for BOTH paths: fragment (real graphics, +8-74%, beats
stock) and compute (+137% on genuine data-parallel compute). DXVK / emulator
compute shaders (blur, post-processing, upscalers) can get a large boost. Kept as
an opt-in (GAMMA_FP16_COMPUTE) since some compute is precision-sensitive; the
fragment fp16 stays the ULTRA default. Source has the gate; next ULTRA rebuild will
expose GAMMA_FP16_COMPUTE on the deployed driver. Patch: turnip-force-fp16.patch.

## compute-fp16 DEFAULT-ON corrupts real titles - keep it OPT-IN (correctness catch)

Tried making compute fp16 default-on too (ULTRA-MAX, driver 16330312). Benched fine
(gamebench 13.9, gpubench_dec 84.6, compute 125.1) BUT it CORRUPTS 3DMark Wild Life
Extreme - the render shows a black band + speckle artifacts (WLE uses a compute
shader whose fp16 demotion breaks it; the inflated 189 score is from rendering less/
wrong). Fragment-only fp16 renders WLE CLEAN. So compute fp16 must stay OPT-IN
(GAMMA_FP16_COMPUTE) - it is a big win (+137%) for compute you know is fp16-safe
(post-processing/upscale) but not blanket-safe. REVERTED: the deployed baseline and
the shipped ULTRA zip stay fragment-fp16-only (16330280, renders every tested title
correctly). Lesson: always screenshot-verify precision changes on a real title.
Also closed two deep avenues this pass: ir3 fp16 vec2-packing needs novel backend
rpt-group formation from independent scalar ops (multi-day, deferred); 16-bit
texture sampling is ALREADY auto-enabled by ir3 when results are consumed at fp16
(so ULTRA's fp16 already gets the texture-bandwidth benefit).

## Texture LOD bias: marginal (+1.8% WLE, within noise) - opt-in env only

Added GAMMA_LODBIAS env (positive texture LOD bias -> sample smaller mips = less
texture bandwidth, for bandwidth-bound content; linear-mipmap samplers only).
Tested on top of ULTRA fp16, WLE (bandwidth-influenced, GPU @1010):
- fp16 baseline: 171
- fp16 + GAMMA_LODBIAS=2.0: 174 (+1.8%, within run variance)
Renders CLEAN (screenshot verified - textures slightly softer but no corruption).
So LOD bias is a marginal, quality-costing lever - NOT worth making default, but
kept as an opt-in env (GAMMA_LODBIAS=<n>) for users squeezing bandwidth-bound
titles. fp16 already picked most of WLE's headroom; the residual is not texture
bandwidth. Deployed driver now carries the option (ULTRA + GAMMA_LODBIAS, default
0 = identical to ULTRA). Patch: turnip-lodbias.patch.

## fp16 is workload-dependent: wins on transcendental/lighting, neutral on matrix-mul

Built a second realistic fragment benchmark, gamebench2 (matrix/transform-heavy:
mat3 multiply, dot, fract, normalize per pixel) to test whether fp16's big lighting
win generalizes. Bind-mount, GPU pinned @1010:
- gamebench2 ULTRA (fp16 on):   10.6 GFLOPS
- gamebench2 GAMMA_NOFP16 (fp32): 10.6 GFLOPS
- gamebench2 stock:              11.6 GFLOPS
fp16 gives ZERO benefit here (10.6 == 10.6), unlike the lighting shader gamebench
(+74%). Turnip also sits ~91% of stock on this matrix-mul pattern. Why: the lighting
shader is dominated by SFU transcendentals (pow/exp/normalize on scalars) where fp16
halves SFU + register pressure; the matrix shader is dominated by fp mul/add that
already pack well at fp32 and whose fp16 form needs the same number of ALU slots
(mad.f16 is not 2x throughput for these dependent chains). So fp16's value is
workload-dependent: it is a large win for transcendental/lighting-bound fragment
work and a wash for arithmetic/matrix-bound work - it never regresses these, which
is why ULTRA (fragment fp16 default-on) is safe as the baseline. gamebench2 added to
the tree as a second fragment-bound characterization benchmark.

## Vertex-shader fp16 (GAMMA_FP16_VERTEX): ~+4% but vertex-bound-only, opt-in

The forced-fp16 path was fragment-only (plus opt-in compute). Extended it to VERTEX
shaders behind a new opt-in env GAMMA_FP16_VERTEX (default OFF). To actually measure
it, added a vertex-bound benchmark (vertbench) - all prior benches are fragment/
compute-bound (a fullscreen triangle = 3 vertices), so they show ZERO vertex effect
(confirmed: gamebench 14.0 == 14.0 with/without vertex fp16). vertbench draws millions
of vertices with a heavy per-vertex transform loop into a 32x32 target so vertex ALU
dominates. GPU pinned, bind-mount:
- iters=64:  fp32 25.6 -> fp16 26.6 Mverts/s  (+3.9%)
- iters=128: fp32 12.9 -> fp16 13.4 Mverts/s  (+3.6%)
- iters=256: fp32  6.6 -> fp16  6.8 Mverts/s  (+3.0%)
Consistent ~+3-4% on vertex-ALU-bound work (normalize/sin/cos on the SFU + fma chains
halve to fp16). It is NOT baked into ULTRA default-on: demoting gl_Position math to
fp16 risks geometry wobble / z-fighting / cracks on real content (position wants fp32),
so it stays OPT-IN like GAMMA_FP16_COMPUTE - safe to enable for vertex-bound titles a
user has verified render clean. On the RG 55G1's real fragment-bound titles (Wild Life,
WLE - GPU 99% saturated on fragment) vertex is not the bottleneck, so default-on would
add position risk for ~0 title FPS. Kept: source gate (turnip-fp16-vertex.patch) +
vertbench in the tree as the vertex-bound characterization bench. Deployed driver
unchanged (still ULTRA+LOD 16330528, renders correctly).

## Constant-integer pow() -> repeated squaring: +20% on fp16 lighting (BIG win)

Root-caused a large avoidable cost in fp16 lighting shaders. ir3 sets lower_fpow so
pow(x, N) is compiled to exp2(N*log2(x)) - a log2 + an exp2 on the a6xx SFU. Those
SFU ops are fp32-only, so under forced-fp16 the compiler wraps every pow() in
fp16->fp32->fp16 conversions. pow(ndh, shininess) (specular) is in nearly every
lighting shader, so this hits real content hard. Mesa already knows repeated squaring
beats the SFU pair, but only ships the recovery pattern for the post-lowered
exp2(log2(x)*8) at N=8. Extended it to every constant positive-integer exponent 5..64
via binary exponentiation (matching the exp2(fmul(flog2(a), N)) post-lowering form so
it fires cleanly after lower_fpow, not racing it). Repeated squaring stays in the
shader's native precision and is MORE accurate than the log/exp roundtrip.

Measured (gamebench realistic lighting, pow(ndh,32.0), GPU pinned, bind-mount):
- fp16 reassoc OFF (exp2/log2): 14.0 GFLOPS
- fp16 reassoc ON  (squaring):  16.8 GFLOPS  (+20%, == hand-squared reference 16.8)
- fp32 reassoc OFF: 8.0 -> ON 8.3 GFLOPS (+3.7%)
Output is bit-for-bit the hand-squared shader (correctness confirmed; squaring is the
more accurate form). Gated on gamma_reassoc (ULTRA default-on; opt out GAMMA_NOFASTMATH).
Baked into the ULTRA driver (vulkan.turnip.ultra.so now 16337896) + Winlator zip
ULTRA-v3. vendor_turnip_ultra.img repacked (debugfs in-place swap, same_process_hal_file
context preserved, e2fsck clean) and staged for a clean foreground flash + real-title
(WLE/WildLife) revalidation next tick. Device still on the prior working ULTRA+LOD
(16330528) this tick. Patch: turnip-pow-squaring.patch. Also added gamebench_pm (the
hand-squared reference variant) to the tree.

## pow-squaring ULTRA: flashed + real-title validated (clean, +0.6/+1.1% on 3DMark)

Baked the pow-squaring pattern into the default-on ULTRA driver (16337896), flashed
vendor_turnip_ultra.img to the device (fastbootd, foreground, single) and validated on
real titles. Deployed-driver sanity (no env, ULTRA default-on): gamebench 16.8 (the +20%
pow win is live vs the old 14.0), gpubench 129 (reassoc intact). 3DMark:
- Wild Life:  723 (prior ULTRA 719, +0.6%), avg 4.34 fps - renders clean
- Wild Life Extreme: 186 (prior ULTRA 184, +1.1%), avg 1.12 fps - renders clean
Screenshot-verified both: WLE mid-run shows the alien-landscape scene (two moons, spires,
terrain) with no black band / speckle (the corruption signature that killed compute-fp16),
and the Wild Life result art relights correctly. So pow-squaring is correctness-safe on
real content. The 3DMark titles gain little because they use little constant-integer-
exponent specular (their pow calls are non-integer / masked), whereas classic Blinn-Phong
lighting (gamebench) gains +20%. Net: the deployed ULTRA is now the pow-squaring build,
strictly >= the prior ULTRA on every measured title and much faster on pow-heavy shaders.
Device left on this validated ULTRA (16337896).

## Transcendental fp16 profiling: single-SFU ops already benefit - no more pow-style wins

After the big integer-pow win, profiled whether the other SFU transcendentals suffer the
same fp16<->fp32 conversion penalty pow did (pow was two chained SFU ops, log2 then exp2,
with an fp32 multiply between). Added three fragment microbenches (gb_exp, gb_trig,
gb_sqrt) each with the given op in the hot loop, measured fp16 vs GAMMA_NOFP16 fp32
(GPU pinned):
- exp2/log2 (fog/HDR): fp16 12.5 vs fp32 7.6  (1.64x)
- sin/cos:             fp16  9.8 vs fp32 7.0  (1.40x)
- sqrt/rsqrt:          fp16 10.5 vs fp32 7.6  (1.38x)
All three ALREADY get a solid fp16 speedup, so there is no pow-style "eliminate the SFU"
opportunity for single-SFU ops - the conversions around a single SFU op are cheap; pow was
uniquely bad only because it chains two. Also tested half-integer exponents (the one place
a manual form might beat the SFU pair): pow(x,1.5)+pow(x,2.5) via exp2/log2 = 11.5 GFLOPS,
manual x*sqrt(x)+(x*x)*sqrt(x) = 11.5 GFLOPS - a TIE, because the manual form still needs an
SFU sqrt. So half-integer pow is NOT worth lowering; the integer-exponent squaring (5..64)
stays the unique large SFU-avoidance win. Conclusion: SFU-avoidance is now exhausted beyond
integer pow; the remaining big fp16 lever is the deep ir3 half-reg vec2 packing (scalar
mad.f16 vectorization, stock 126 vs Turnip 85). Microbenches kept in tree as characterization
tools. Device unchanged (validated ULTRA 16337896); no flash this tick.

## ROLLED BACK: pow-squaring (ULTRA v3) causes flickering / black textures

Field reports: the ULTRA v3 driver (constant-integer pow() -> repeated squaring,
16337896) causes heavy flickering and black textures on real content. Root cause:
under forced fp16 the repeated-squaring chain for pow(x, N) overflows to inf/NaN when
the base x > 1 (fp16 max is 65504, and x^32 for x just above 1 blows past it), whereas
the exp2/log2 SFU path it replaced clamped/handled those ranges. The +20% lighting
microbench win was real but not worth the visual corruption on shipping games.

ROLLED BACK to the pre-v3 ULTRA (fp16 + reassoc + dw_noubwc, NO pow-squaring, 16330280
= ULTRA v1/v2). Deployed driver, GammaOSCoreVendor, and the tree's vulkan.turnip.ultra.so
are all reverted to 16330280; the v3 binary is kept as vulkan.turnip.ultra_powi_v3.so for
record. Source: the pow-squaring nir pattern is now gated on a new gamma_powi option
(GAMMA_POWI env, OPT-IN ONLY, never default-on) instead of gamma_reassoc, so a default
ULTRA rebuild no longer includes it. To revisit safely it needs a base<=1 guard (only
lower pow when the base is provably in [0,1], e.g. saturated dot products) before it can
go back into ULTRA. Device-verified: pre-pow ULTRA boots and renders clean.

## sysmem/flushall are free on single-pass renders (cost is emulator-only)

Cron tick 2026-08-29. Measured the TU_DEBUG=sysmem and =flushall cache/tiling
workarounds (the community "A12 fix" levers, now GAMMA_SYSMEM/GAMMA_FLUSHALL opt-ins)
on the deployed selective-fp16 ULTRA (16338592), GPU pinned:
- gfxbench 1080p single-pass render: default(GMEM) 60.2, sysmem 60.3, flushall 60.2
  GFLOPS - identical within noise. mpix/s 14.7 all three.
So on a single render pass with one fullscreen triangle these flags cost ~0. Their real
cost (GMEM tile store/load avoided, or per-submit cache flush added) only appears with
many small passes / render-to-texture / feedback loops - i.e. exactly the DXVK/VKD3D/
RPCS3 emulator workloads they fix. Implication: baking flushall into the GameNative
driver has ~zero downside on simple content, and choosing sysmem-vs-flushall-vs-neither
for MGS4 must be decided by a real in-game A/B (microbenches can't distinguish them). A
multi-pass render-to-texture microbench would measure it offline (next lever).
Also recorded this tick (deployed selective-fp16 ULTRA, GPU@1010): gpubench plain compute
52.4 (reassoc's 127 is on the constant-coefficient FMA variant, not plain compute),
gamebench 14.0, gfxbench 60.2, gb_exp 12.5, gb_trig 9.8, gb_sqrt 10.6.

## Multi-pass render-to-texture bench: sysmem >= GMEM >= flushall on the RT pattern

Built rtbench (added to the tree): ping-pongs between two color images, each pass
samples the previous result and renders into the other with read-after-write barriers -
the DXVK/VKD3D/RPCS3 emulator pattern the single-pass benches can't capture. Deployed
selective-fp16 ULTRA, GPU pinned, passes/s (higher better):
- 512x512, 600 passes:  GMEM 5629,  sysmem 5730 (+1.8%),  flushall 5539 (-1.6%)
- 1024x1024, 400 passes: GMEM 1433, sysmem 1439 (+0.4%),  flushall 1417 (-1.1%)
- 256x256, 1000 passes:  GMEM 20856, sysmem 20827 (~0)
So on RT-heavy content sysmem is neutral-to-slightly-faster than GMEM tiling (peak +1.8%
at 512, it avoids the tile store/load), and flushall is consistently ~1-1.6% slower (the
per-submit cache flush). Pure-perf ordering: sysmem >= GMEM > flushall. Since the user
found flushall best for MGS4, that preference is a CORRECTNESS win (flushall fixes a
coherency corner these correct-in-all-modes benches don't expose), not a speed one -
sysmem is faster where it renders correctly. Shipped a GameNative sysmem variant
(gamenative_sysmem.so 16338920, zip GameNative-sysmem-v1) alongside the flushall one so
MGS4 can be A/B'd; sysmem is the better default if it renders clean.

## Selective fp16 real-title benefit is workload-dependent (3DMark pass)

Fresh 3DMark on the deployed selective-fp16 ULTRA (16338592), fan max, GPU pinned, both
screenshot-verified rendering clean (no black textures):
- Wild Life (1440p):  650  (3.89 fps)
- Wild Life Extreme (4K): 179 (1.07 fps)
Compared to prior baselines: blanket-fp16 ULTRA WL 719 / WLE 184-186; aggressive (no
fp16) WL 649 / WLE 167; stock blob WL 700 / WLE 174. So:
- On WLE (4K, fragment-ALU-bound) selective fp16 = 179, i.e. +7% over aggressive 167 and
  above stock 174 - it keeps most of the fp16 gain (blanket was 184).
- On Wild Life (1440p, texture-bound) selective fp16 = 650 ~= aggressive 649, i.e. the
  entire ~70pt (10%) fp16 win from blanket-fp16 (719) came from the texture-coordinate
  math that selective now protects. Here we sit below stock (650 vs 700).
- On gamebench (pure ALU, no textures) selective = blanket = 14.0 (full gain).
So selective fp16 recovers correctness with full benefit on ALU/emulator-bound content
(MGS4, WLE, gamebench) and near-zero benefit on texture-bound content (Wild Life). The
fp16 speed and the black textures are the same tex-coord math - can't have both blindly.
NEXT LEVER: narrow the tex-coord protection (protect only large/atlas-texture UVs, or
only the final UV op rather than the whole backward slice) to recover some Wild Life fp16
without reintroducing black textures - measure black-texture risk via screenshot diff.

## fp16 codegen gap quantified: Turnip 85.1 vs stock 126 (~48% half-reg-packing prize)

Ran gfxbench_f16 (a shader with explicit float16_t math - native fp16, independent of our
forced-fp16 demotion) on the deployed selective-fp16 ULTRA: 85.1 GFLOPS (20.8 mpix/s),
matching gfxbench_f16feat 85.1. This confirms the long-noted "stock fp16 126 vs Turnip 85"
gap exactly: the stock Qualcomm blob does ~126 on the same fp16-heavy shader, so Turnip
leaves ~48% on the table for native fp16 workloads. Root cause: the a6xx can pack two
independent scalar fp16 ops into one 32-bit register slot and issue them together (vec2
half-reg / mad.f16 pairing); the stock blob does this well, ir3 often does not, leaving
fp16 ops scalar at half throughput. This is the single biggest untapped Turnip lever on
this GPU - but it is deep ir3 BACKEND work: ir3_base_options has lower_to_scalar=true, so
NIR-level nir_opt_vectorize cannot help (everything is scalarized before the backend); the
packing has to happen in ir3's rpt-group formation / scheduler / register allocator. IR3
already forms rpt groups (IR3_DBG_EXPANDRPT is off by default), it just does not pair
independent scalar fp16 chains as aggressively as the blob. Candidate approaches (multi-
tick): teach ir3_rpt/ir3_sched to co-issue independent same-op fp16 scalars into vec2, or
rebase to newer Mesa main (may have improved a6xx fp16 packing) and re-measure. Prize if
closed: up to ~1.5x on fp16-bound fragment work (gamebench, WLE, and DXVK/RPCS3 shaders).

## NEGATIVE: NIR-level fp16 vectorization does not close the packing gap

Tested the obvious first attempt at the fp16 packing win: a GAMMA_FP16_PACK-gated
nir_opt_vectorize with a callback returning width 2 for 16-bit float ALU, placed as the
last NIR pass in ir3_optimize_loop (after the opt-loop's nir_lower_alu_to_scalar so it
would not be undone). Result: ZERO change - gfxbench_f16 85.1 with and without the pass,
gamebench (forced fp16) 14.0 both. Why: the fp16-heavy shaders are scalar DEPENDENT
chains, not batches of independent same-op scalars. gfxbench_f16's hot loop is
`a=a*b+c; b=b*c+d; c=c*d+a; d=d*a+b;` - four cross-dependent fp16 mads; there is nothing
for nir_opt_vectorize to pair (different operands, RAW dependencies). So the stock blob's
126-vs-85 lead is NOT NIR vectorizable - it comes from the ir3 BACKEND: how it schedules
/ dual-issues / co-issues semi-independent scalar fp16 mads and allocates half-registers.
Confirms the packing lever lives in ir3_sched / ir3_ra / ir3_rpt (co-issue independent
scalar fp16 into a half-reg pair), a much deeper change than any NIR pass. Reverted the
no-op pass (source clean). Deployed driver unchanged (selective-fp16 ULTRA 16338592).

## Compute fp16 = +141% (2.4x), reaches the a6xx fp16 peak; fragment gap is scheduling

Measured GAMMA_FP16_COMPUTE (forced fp16 on compute shaders, opt-in) on gpubench,
deployed driver, GPU pinned:
- gpubench fp32:              52.4 GFLOPS
- gpubench GAMMA_FP16_COMPUTE: 126.2 GFLOPS  (+141%, 2.4x)
The 126.2 lands right on the ~126 "stock fp16" figure - i.e. compute fp16 PACKS PERFECTLY
here and hits the a6xx fp16 throughput ceiling. Contrast the fragment native-fp16
dependent-chain bench gfxbench_f16 which sits at 85. So the 85-vs-126 fp16 gap is NOT a
universal ir3 packing deficiency: compute (independent/parallel fp16 ALU) reaches the
peak; only the fragment dependent-chain case (each mad waits on the previous) falls short,
which is a latency/scheduling problem, not packing. Deployability: GAMMA_FP16_COMPUTE stays
OPT-IN - it corrupts 3DMark Wild Life Extreme (WLE uses a compute shader broken by fp16,
the black-band/speckle seen earlier). To ship it would need a SELECTIVE compute fp16 (same
backward-slice idea as fragment: protect the precision-critical compute ops) - a candidate
for content known to be fp16-safe (post-processing, upscale, some DXVK/RPCS3 compute). For
now it is a documented 2.4x lever for opt-in compute-heavy workloads. Suite this tick
(deployed selective-fp16 ULTRA): gpubench 52.4, gamebench 14.0, rtbench(512) 5662.

## sysmem validated on 3DMark: ~2% below GMEM on real titles (stays GameNative-only)

Flashed the sysmem GameNative variant (ULTRA + baked sysmem, 16338920) to /vendor and ran
3DMark, screenshot-verified rendering clean (no black textures / corruption):
- Wild Life:  637 (3.82 fps)  vs deployed GMEM 650  (-2.0%)
- Wild Life Extreme: 176 (1.06 fps) vs deployed GMEM 179 (-1.7%)
So sysmem is ~2% SLOWER than GMEM tiling on these tile-friendly real titles - as the
rtbench data predicted (sysmem only wins on RT-heavy multi-pass content; WL/WLE are not
that). Confirms the shipped split is correct: /vendor keeps GMEM (selective-fp16 ULTRA,
best for native/tile-friendly content), and sysmem stays a GameNative-only opt-in for the
emulator RT pattern where it wins. Reverted /vendor to selective-fp16 ULTRA (16338592).
Also this tick: mesa-turnip HEAD is 2026-08-27 (d245b965) - already bleeding-edge Mesa
main, so the "rebase to newer Mesa" lever is EXHAUSTED (nothing newer to pull; any a6xx
fp16-scheduling improvement would have to be authored/upstreamed, not fetched).

## NEGATIVE: wave size (thread64) does not help the fp16 dependent chain; gap exhausted

Tested IR3_SHADER_DEBUG=thread64 (prefer 64-thread wave vs the deployed 128-wide
fragment waves) on the latency-bound fp16 benches: gfxbench_f16 84.9 vs 85.1, gamebench
14.0 vs 14.0, gpubench 52.4 vs 52.5 - no difference. So the fragment fp16 gap is NOT
wave-occupancy limited; it is per-wave instruction latency on the dependent mad chain.
Combined with the prior negatives (NIR nir_opt_vectorize no help, Mesa already at
bleeding-edge 2026-08-27, and compute fp16 already reaching the 126 peak), the fragment
fp16 codegen gap (85 vs stock 126 on dependent chains) is now EXHAUSTED via every
tractable lever - env flags, wave size, NIR passes, config, Mesa version. Closing it would
require actual ir3 backend work (co-issue independent scalar fp16 mads, or a lower-latency
fp16 mad path) = Mesa upstream contribution territory, high-risk / multi-day, not a cron
lever. NOTE this gap only bites pure fp16-ALU-bound fragment shaders (rare in real content
where texture/bandwidth dominates); it does not affect the shipped driver's real-title
scores. Perf-lever inventory is now largely closed; the loop's remaining value is
GameNative/emulator compatibility tuning and keeping artifacts/docs current.

## Experimental GameNative maxfp16 variant (compute fp16 for RPCS3/DXVK)

Built and shipped an EXPERIMENTAL GameNative driver (gamenative_maxfp16.so 16338872,
zip GameNative-maxfp16-EXPERIMENTAL-v1) = ULTRA (selective fragment fp16) + flushall +
FORCED fp16 on COMPUTE shaders (GAMMA_FP16_COMPUTE default-on in this build only). The
compute fp16 lever is +141% (gpubench 52.4 -> 126.2, hits the a6xx fp16 peak) and could
be a large win for emulators that lean on compute (RPCS3/DXVK do texture decode + format
conversion in compute) IF the game's compute is fp16-safe. It is NOT deployable generally
- it corrupts fp32-dependent compute (black-bands 3DMark WLE). So it stays a user-A/B-only
experimental GameNative variant: if MGS4 renders clean with it, keep it for the speed; if
it corrupts, use the regular GameNative-flushall build. Deployed /vendor driver unchanged
(selective-fp16 ULTRA 16338592); env-gated Mesa source restored (all GAMMA_* opt-in).

## Periodic regression check (deployed selective-fp16 ULTRA): stable, no regression

3DMark on the deployed driver, fan max, GPU pinned, both screenshot-verified rendering
clean (no black textures): Wild Life 649 (3.89 fps), Wild Life Extreme 176 (1.06 fps) -
matching the prior baseline (WL 650 / WLE 179) within run-to-run noise. Shell suite also
stable: gpubench 52.4, gamebench 14.0, gfxbench 60.3. No regression; the shipped driver
holds its numbers.

## NEGATIVE: safe (fsat-guarded) pow-squaring - avenue fully closed

Attempted the documented "base<=1 guard" to make pow-squaring safe: square fsat(base)
instead of base, so pow(x,N) cannot overflow fp16 to inf/NaN for base>1 (the black-texture
cause) while staying identity for specular pow(ndh,N) where ndh is already in [0,1].
Measured on gamebench (ULTRA env, GAMMA_POWI=1): 14.0 - no change. Isolating it, the BARE
(non-fsat) pow-squaring ALSO gives 14.0 now, i.e. the pattern does not fire at all under
the current gamma_powi gate. It only fired in the original session when gated on
gamma_reassoc + GAMMA_FASTMATH, because gamma_force_fast_math clears fp_math_ctrl and
supplies the `contract` allowance that the `exp2(contract)(...)` match requires; the
opt-in GAMMA_POWI path does not enable that contract flag, so the match misses. Since
pow-squaring is deprecated regardless (it blacks textures on real content) and the safe
fsat form yields nothing even in the microbench, the entire pow-squaring avenue is now
CLOSED - not worth re-wiring a contract-enable path for a lever that cannot ship. Source
reverted to the committed state (bare 'a', gamma_powi opt-in, unused). Deployed driver and
all shell benches unchanged (gamebench 14.0, gpubench 52.4).

## NEGATIVE: TU_DEBUG=noconform is negligible (~within noise), not worth the risk

Tested noconform (disable Turnip conformance workarounds - the theory being games do not
hit the conformance edge cases the workarounds guard) on the deployed driver, GPU pinned:
gfxbench 60.1->60.3, rtbench(512) 5663->5702 (+0.7%), gamebench 14.0->14.0. Best case
+0.7% on the RT pattern, everything else within run-to-run noise. It also does NOT stack
with sysmem (rtbench sysmem 5709 vs sysmem+noconform 5701). So the conformance workarounds
carry no meaningful overhead on real workloads, and disabling them only risks subtle
rendering bugs on the content they guard - not worth adopting for <1%. Added to the
tested-neutral list. Deployed driver + benches unchanged.

## CORRECTION: flushall costs -4% to -10% on real titles (not ~free); prefer sysmem

Validated the GameNative-flushall variant (ULTRA + baked flushall, 16338888) on real
3DMark, screenshot-verified rendering clean:
- Wild Life:  585 (3.51 fps)  vs deployed GMEM 649  (-9.9%)
- Wild Life Extreme: 172 (1.04 fps) vs GMEM 179 (-3.9%)
This CORRECTS the earlier single-pass microbench reading (gfxbench: flushall == GMEM
"free"). On a real multi-pass title the per-submit cache flush is expensive: -10% on Wild
Life (many submits per frame), -4% on the more GPU-bound WLE. Full real-title ranking of
the GameNative options now measured:
- GMEM (deployed):  WL 649 / WLE 179
- sysmem:           WL 637 / WLE 176  (-2%)
- flushall:         WL 585 / WLE 172  (-10% / -4%)
So on native content GMEM > sysmem > flushall, and flushall is by far the most expensive.
For emulators, sysmem (-2%) is the much cheaper coherency option than flushall (-10%);
flushall should only be used if a title needs its stronger per-submit flush that sysmem's
tiling-bypass does not provide. Recommendation for GameNative: try sysmem first, fall back
to flushall only if sysmem still corrupts. Reverted /vendor to selective-fp16 ULTRA
(16338592). Lesson: microbenches under-report flushall's cost - real multi-submit titles
are the true signal.

## SHIPPED: compute round-robin dispatch baked into ULTRA (v5, +5.7% compute, graphics-neutral)

Baked TU_DEBUG=computeroundrobin (TU_DEBUG_COMPUTE_ROUND_ROBIN) default-on into the deployed
ULTRA driver, opt-out via GAMMA_NO_COMPUTE_RR. It round-robins compute workgroups across the
SP cores instead of the default packing. Measured, GPU pinned 1010 MHz:
- gpubench (compute):  52.4 -> 55.4 GFLOPS  (+5.7%, stable across 3 runs each)
- gfxbench (graphics): 60.3 (neutral)
Built ULTRA (FASTMATH+FP16 default-on via seds, then reverse-sed to opt-in), driver
16338592 -> 16338864 (+272 bytes of dispatch code). Flashed vendor_a via fastbootd, booted
clean, driver confirmed on device (16338864).

Real-title 3DMark validation (screenshot-verified rendering clean, no black textures, WLE's
compute shaders NOT corrupted - the key check for a compute-dispatch change):
- Wild Life:         647 (3.88 fps)  vs v4 650  (neutral, within variance)
- Wild Life Extreme: 179 (1.07 fps)  vs v4 179  (identical)
Compute-using content (RPCS3/DXVK compute, upscalers) gets the +5.7% for free; native
graphics is unaffected. Shipped as ULTRA-v5 (GammaOS-Turnip-Adreno613-ULTRA-v5.adpkg.zip,
driver 16338864). Deployed driver + selfbuilt canonical (vulkan.turnip.ultra_safefp16.so)
updated. Device left on the working v5 driver. Mesa sources restored to env opt-in (never
git-checkout - reverse-sed only, as mesa has no committed gamma baseline).

## Vertex fp16 characterized + made geometry-safe (opt-in GAMMA_FP16_VERTEX)

Characterized the vertex-shader forced-fp16 lever (GAMMA_FP16_VERTEX, previously untested)
on vertbench, GPU pinned 1010 MHz, on the deployed v5 driver via bind-mount:
- fp32 baseline:                    23.2 - 23.3 GFLOPS (stable across reruns)
- vertex fp16 (blanket, no guard):  24.0 GFLOPS  (+3.2%)
So vertex-ALU-bound work gets a small real win from fp16. BUT blanket vertex fp16 demotes
the clip-space position math too, which loses position precision and cracks / jitters
geometry (the vertex analogue of the fp16 black-texture failure) - which is why it was
opt-in and unused.

Fix: extended the selective keep-set (gamma_fp16_build_keep) to also protect the position
feeder chains in non-fragment stages - VARYING_SLOT_POS (gl_Position), VARYING_SLOT_PSIZ
(point size) and the clip/cull distance outputs are kept fp32, exactly as FRAG_RESULT_DEPTH
is protected in the fragment stage. Measured the protected variant:
- vertex fp16 (position-protected): 24.0 GFLOPS  (+3.2%, identical to blanket)
The protection is FREE: 24.0 protected == 24.0 blanket, because the position math is a tiny
fraction of the vertex ALU. So GAMMA_FP16_VERTEX now keeps its throughput win without the
geometry-corruption risk.

Residual: interpolated texture-coordinate varyings written by the vertex shader are still
demoted (cross-stage, not protected here), so GAMMA_FP16_VERTEX stays OPT-IN, not a default -
and it gives ~0 on fragment-bound real titles (Wild Life / WLE), so there is no reason to
turn it on by default. Value is the now-safe lever for vertex-ALU-bound content. Fragment and
compute paths are byte-identical (the keep-set refactor only adds the non-fragment branch), so
the deployed v5 driver is unchanged; no vendor reflash. Source captured in
turnip-force-fp16.patch; candidate built as vulkan.turnip.vtxfp16safe.so. Deployed driver
remains selective-fp16 + compute-round-robin v5 (16338864), device left working.

## Stock-blob gap profiled + UBWC is a +43% emulator render-to-texture win (GameNative-ubwc variant)

Bind-mounted the STOCK Qualcomm Adreno 64-bit blob (/work/55g1_super/qcom_gpu/vulkan.adreno.so,
4041984 bytes, Vulkan 1.1) and ran the full suite vs our deployed v5, GPU pinned 1010 MHz, to
quantify where Turnip trails the proprietary driver:

| bench          | stock blob | our v5 | gap |
|----------------|-----------:|-------:|-----|
| gpubench (compute)        | 128.9 | 55.4 | stock +133% |
| gamebench (lighting frag) |   8.8 | 14.0 | WE +59% (our fp16) |
| gfxbench                  |  77.8 | 60.1 | stock +30% |
| gfxbench_f16              | 127.4 | 84.9 | stock +50% (fp16 codegen gap) |
| vertbench                 |  22.7 | 23.2 | parity |
| rtbench (multi-pass RT)   |  8533 | 5686 | stock +50% |

Two big real gaps: compute throughput (stock's scheduler/packing) and multi-pass
render-to-texture (rtbench) - the latter is exactly the DXVK/VKD3D/RPCS3 emulator pattern.
Chased the rtbench gap: it is UBWC. We disable UBWC by default (a measured ~7% GAIN on native
tiled 3DMark: WL 606->648, WLE 158->170), but UBWC is a large WIN on bandwidth-bound multi-pass
RT. Measured on the deployed v5 via the GAMMA_UBWC env lever:
- rtbench UBWC off: 5636-5710   UBWC on: 8062-8118   => +42-43%
- everything else (gpubench/gamebench/gfxbench/gfxbench_f16/vertbench): neutral within noise
- UBWC+SYSMEM stacks slightly on top of UBWC alone (8105-8112 best)
So UBWC is neutral on native microbenches but recovers most of the rtbench gap to stock (8118 vs
stock 8533). UBWC is lossless framebuffer compression, so it carries NO correctness risk (no
black textures) - it is a pure bandwidth/perf tradeoff: ~7% worse on native tiled titles, ~43%
better on RT-pingpong emulator chains.

Shipped as GameNative-ubwc-v1 (ULTRA-v5 + UBWC-on + sysmem-on baked, driver 16338840). Baked
build verified via bind-mount with NO env vars: rtbench 8118 (+43%), gfxbench 60.4, gamebench
14.0 (fp16 kept), gpubench 55.4 (compute-RR kept). NOT flashed to /vendor and NOT the default -
UBWC's native cost makes it emulator-only; it is imported into Winlator/GameNative as an
AdrenoTools driver like the sysmem/flushall variants. Deployed device driver stays ULTRA-v5
(UBWC off, 16338864). Recommendation: for RT/post-process-heavy GameNative titles (MGS4) try
GameNative-ubwc; for coherency-only issues use GameNative-sysmem. NOTE for a future tick: the
compute gap (stock 128.9 vs 55.4) is the next big lever - our FASTMATH reassoc reaches parity
only on pure FMA-chain patterns, not gpubench's compute shader; worth profiling why.

## Compute gap profiled (stock 128.9 vs 55.4): latency-bound dependent FMA, wave-size lever inapplicable (negative)

Chased the largest stock-vs-Turnip gap from last tick: gpubench compute 128.9 (stock) vs 55.4
(ours), a 2.3x deficit. Findings:
- gpubench is a DEPENDENT FMA chain (a = a*b+c four times per loop iter, each depends on the
  prior). Explicit fma() vs a*b+c are identical (both 55.4) so instruction fusion is already
  optimal; gpubench_precise 55.4 too, gpubench_dec 36.5 (different pattern).
- ir3 disasm of the inner loop shows each mad.f32 carries (nop3): a 4-cycle result latency
  between dependent mads (4 mad + nops = latency-bound, not throughput-bound). Stats:
  "2 full regs, 16 max_waves, 0 double_threadsize, 1 loops".
- Compute runs single-threadsize (wave64). Tried forcing wave128 for compute via a new
  GAMMA_CS_WAVE128 lever (ir3_should_double_threadsize): NO effect, disasm still reports
  0 double_threadsize. Reason: gpubench's workgroup is local_size_x=64, so the wave is clamped
  to the 64-wide workgroup - a 128-wide wave would leave half its lanes idle. The driver is
  already optimal here; the wave-size lever cannot apply to <=64-wide workgroups.
- The fragment double-threadsize patch (our +1.7x fragment ALU win, 42->72 GFLOPS) is correctly
  fragment-only (MESA_SHADER_FRAGMENT); a6xx compute wave sizing is workgroup-bound.

Conclusion: the compute gap is dependent-FMA latency hiding / dispatch concurrency, NOT
instruction selection, fusion, or wave size. The compute-round-robin dispatch already shipped in
v5 addresses part of this (+5.7%); the residual is HLSQ/firmware workgroup-scheduling concurrency
that the compiler does not control. Reverted the GAMMA_CS_WAVE128 lever (proven no-op on
workgroup<=64, unverifiable elsewhere - kept source clean). No driver change; device stays on
ULTRA-v5 (16338864). Recorded so future ticks do not re-chase wave-size for the compute gap.
Note: real game content is largely fragment-bound where we lead (gamebench 14.0 vs stock 8.8);
the compute deficit mainly touches DXVK/RPCS3 compute passes.

## fp16 codegen audited (our packing/SFU already optimal) + periodic 3DMark validation of v5

Audited the fp16 codegen gap (gfxbench_f16 85 vs stock 127) by disassembling the shaders,
following up the compute-gap finding. Results:
- gfxbench_f16's inner loop is a DEPENDENT mad.f16 chain (hr2.x feeds hr3.x ...), scalar with
  (nop1)/(nop3) latency stalls. It CANNOT be rpt-packed into vec2 half-registers (rpt needs
  independent consecutive-register ops with a uniform source pattern) - so the "vec2 fp16
  packing" lever does not apply to this dependent microbench. The stock 127 edge is on the same
  unpackable chain, i.e. hardware fp16 issue/conversion, not a compiler-addressable packing win.
- wave128 (our fragment double-threadsize) vs wave64 (IR3_SHADER_DEBUG=thread64) is IDENTICAL on
  gamebench (14.0), gfxbench (60.2) and gfxbench_f16 (85.3/85.2). So these fragment benches are
  ALU-throughput-bound, not occupancy-bound - our double-threadsize is throughput-neutral here
  (its win is on other, occupancy-bound shaders) and more waves would not help.
- Transcendentals already run on the 2x-rate fp16 SFU: gb_exp disasm shows 16-bit frsq / fexp2 /
  flog2 (fp16), not fp32. No missed fp16-SFU opportunity; gb_exp 12.5 is the fp16 SFU ceiling.
- gamebench FRAG has 74 cat0 (nops) + 79 sstall: heavily texture/SFU-latency bound, yet we still
  beat stock (14.0 vs 8.8) because forced fp16 halves the ALU work.

Conclusion: our codegen (fusion, fp16 demotion, fp16 SFU, wave sizing) is already near-optimal;
the residual synthetic-microbench gaps are hardware dependent-chain latency that does not reflect
real content, where we lead (gamebench +59% vs stock). No compiler change is warranted from the
microbench gaps; recorded so future ticks stop re-chasing them.

Periodic 3DMark pass on the deployed v5 driver (2 ticks since last flash), GPU pinned, both
screenshot-verified rendering clean (no black textures):
- Wild Life:         649 (3.89 fps)   [was 650]
- Wild Life Extreme: 178 (1.07 fps)   [was 179]
Deployed ULTRA-v5 (16338864) confirmed stable and correct. Device left on the working driver.

## UBWC native cost measured on current v5 (WL -7.1% / WLE -4.5%): confirms GameNative-only, not default

Tested whether UBWC-on could become the shipped native default, given its +43% emulator
render-to-texture win (last tick). Built a clean ULTRA+UBWC-on driver (no sysmem, to isolate
UBWC, 16338840), flashed it to /vendor, and ran real 3DMark vs the deployed v5 (UBWC off):

| test               | v5 (UBWC off) | ULTRA+UBWC on | delta |
|--------------------|--------------:|--------------:|------:|
| Wild Life          | 649           | 603           | -7.1% |
| Wild Life Extreme  | 178           | 170           | -4.5% |

Both screenshot-verified rendering clean (UBWC is lossless, so no corruption - only a bandwidth
tradeoff). The native cost precisely matches the historical figure (WL 648->606 ~-7%). So UBWC-on
is confirmed NOT viable as the native default: it costs 5-7% on native tiled titles while giving
+43% only on the emulator RT-pingpong pattern. Decision stands: UBWC stays in the GameNative-ubwc
variant (imported into Winlator/GameNative for RT/post-process-heavy titles like MGS4), and the
shipped native default remains ULTRA-v5 (UBWC off, 16338864). Reflashed the device back to v5;
device verified booted on the working driver. This closes the "should UBWC be default" question
with current-driver real-title numbers rather than the stale note.

Also this tick: confirmed the transcendental benches (gb_exp 12.5 / gb_trig 9.8 / gb_sqrt 10.6)
are SFU-THROUGHPUT-bound, not occupancy-bound - wave64 (16 waves) == wave128 (8 waves) on all
three (identical to the µs), so the 9 cat4 SFU ops per fragment saturate the SFU and more waves
cannot help. Another hardware ceiling, not a compiler lever.

## Compute fp16 (+124%, near stock) confirmed to BLACK-SCREEN WLE: opt-in only, never default (negative)

Followed up the compute gap with the compute-fp16 lever, the single biggest remaining throughput
lever. Measured GAMMA_FP16_COMPUTE on gpubench: 55.4 -> 124.0 GFLOPS (+124%), reaching the stock
blob's 128.9 - i.e. compute fp16 fully closes the compute gap (the deficit was fp32 vs fp16 ALU
rate, not scheduling). Compute address math is integer so fp16 does not touch it; the risk is
value precision.

Built ULTRA-v5 + baked blanket compute fp16 (fragment stays selective, driver 16338680), verified
via bind-mount (gpubench 124.0 with no env, gamebench 14.0 unchanged - fragment path intact),
flashed it, and ran WLE (which uses compute passes):
- WLE renders FULLY BLACK (screenshot-verified: black frame, FPS counter still advancing at frame
  962 - the compute pass executes but produces black output). Severe value-precision corruption,
  not banding.
This definitively confirms the historical note: blanket compute fp16 corrupts WLE. The corruption
is in the computed VALUES (a lighting/luminance/depth compute pass whose fp16 result collapses to
black), which a selective keep-set cannot fix without per-shader semantic knowledge (unlike
fragment texcoords or vertex position, there is no generic "protect this output" rule for an
arbitrary compute result). So compute fp16 cannot be made safe generically.

Decision: compute fp16 stays OPT-IN (GAMMA_FP16_COMPUTE) and in the experimental
GameNative-maxfp16 variant only, never a default. Native default remains ULTRA-v5 (16338864).
Reflashed the device back to v5, verified booted on the working driver. Mesa source restored to
opt-in. Recorded with a screenshot so this is not re-attempted as a default.

## GameNative RT lever matrix across sizes: UBWC+sysmem optimal, benefit GROWS with RT size

Ran the full emulator render-to-texture lever matrix on the deployed v5 (env levers, no flash) at
two RT sizes to settle the definitive GameNative recommendation and check how UBWC scales:

| config              | RT 512 (passes/s) | RT 1024 (passes/s) |
|---------------------|------------------:|-------------------:|
| GMEM (default)      | 5548              | 1414               |
| UBWC                | 7987 (+44%)       | 2069 (+46%)        |
| UBWC + SYSMEM       | 8018 (+44.5%)     | 2072 (+46.5%)      |
| UBWC + FLUSHALL     | 7875 (+42%)       | 2054 (+45%)        |
| SYSMEM alone        | 5502 (-0.8%)      | 1395 (-1.3%)       |

Findings:
- UBWC is the dominant RT lever (+44% at 512, +46% at 1024). The win GROWS with render-target
  size because larger RTs are more bandwidth-bound - so at real emulator game resolutions
  (720p-1080p render targets, bigger than these squares) UBWC should help at least as much,
  strengthening the case for RT/post-process-heavy titles like MGS4.
- UBWC+SYSMEM is marginally the best combo (8018 / 2072), sysmem adding ~0.4% on top of UBWC.
  This is exactly what GameNative-ubwc-v1 bakes, so that shipped variant is confirmed optimal.
- UBWC+FLUSHALL is slightly worse than UBWC+SYSMEM at both sizes (flushall's per-submit cost),
  so sysmem is the right coherency partner for UBWC, not flushall.
- SYSMEM alone (no UBWC) is neutral-to-slightly-negative on this RT pattern; its value is
  coherency for titles that need direct-to-sysmem, not raw RT throughput.

No driver change: this validates the already-shipped GameNative-ubwc (UBWC+sysmem) as the optimal
emulator RT driver and quantifies that it scales with RT size. Device stays on ULTRA-v5
(16338864); native default correctly keeps UBWC off (its -7% native cost, measured last tick).

## fp16 half-register packing CONFIRMED WORKING (new gfxbench_f16v4 bench): the deep codegen win is already implemented

Settled the long-standing "ir3 half-reg vec2 fp16 packing" question by building a PACKABLE fp16
bench. The existing gfxbench_f16 is a near-dependent scalar chain (a,b,c,d cross-dependent) which
cannot be rpt-packed - that is why it sits at 85 vs stock 127, and why prior ticks could not close
it. gfxbench_f16v4 instead runs an f16vec4 with four INDEPENDENT lanes (each lane its own chain),
the packable case real shaders hit (vec3/vec4 colour and lighting math).

Result on the deployed v5, GPU pinned:
- gfxbench_f16   (scalar/near-dependent): 512 iters x 4 fp16 mad  = 0.0996s
- gfxbench_f16v4 (4 independent lanes):   512 iters x 16 fp16 mad = 0.1721s
So 4x the fp16 mads run in only 1.73x the time = ~2.3x throughput per mad on the packable form.
Disasm confirms the mechanism: the loop emits (rpt1)mad.f16 (half-register-packed, 2 lanes per
issue) for the consecutive-source lanes plus scalar mad.f16 for the rest, and reports 0 sstall /
0 systall - cleanly pipelined, no stalls. So ir3 DOES pack independent fp16 lanes into vec2
half-registers, and 2-wide (rpt1) is the correct/optimal packing for fp16 on a6xx (two halves per
32-bit register).

Conclusion: the "deep fp16 codegen win" is already implemented and working in our driver. The
synthetic gfxbench_f16 gap to stock is purely a dependent-chain artifact of that microbench, not a
missing packing optimization - real vectorized fp16 shader math (where we already beat stock on
gamebench, 14.0 vs 8.8) packs and pipelines correctly. Added gfxbench_f16v4 as a permanent
diagnostic. No driver change; device stays on ULTRA-v5 (16338864).

## DXVK saturate()/clamp folds to the free (sat) modifier - zero overhead (new gb_sat bench)

saturate() / clamp(x,0,1) is one of the most frequent operations in translated D3D shaders
(DXVK/VKD3D emit it constantly for colour and lighting). Tested whether our compiler folds it into
the a6xx free (sat) output modifier or emits explicit min/max ALU. Built gb_sat (a non-foldable
loop of four interdependent clamp(a*..-b,0,1) per iteration - an earlier constant-converging
version got the whole loop folded to a constant, 165 GFLOPS, which is why the input must stay
varying) and disassembled it on the deployed v5:
- 4 (sat) modifiers per iteration, 0 explicit min.f / max.f ALU ops.
So every clamp(x,0,1) compiles to a (sat) bit on the producing mad/add - it costs nothing. DXVK's
pervasive saturate() carries zero ALU overhead on Turnip here; no optimization is available or
needed. gb_sat runs 84.9 GFLOPS (the clamps are free on top of the mad chain).

This completes a sweep of the common DXVK/D3D shader patterns, all confirmed already-optimal in our
driver: fp16 vec2 half-register packing (gfxbench_f16v4, prior tick), saturate->(sat) (this tick),
full nir_fp_fast_math reassociation, and preamble constant hoisting. No native-side compiler win
remains from these. Added gb_sat as a permanent diagnostic. No driver change; device on ULTRA-v5.

## Texture-sampling path profiled (new texbench): Turnip LEADS stock (+9.6%), so WL gap is NOT texturing

Wild Life is texture-bound and we trail stock there (649 vs 700), so the hypothesis was that our
texture-unit / sampler path is slower. Built texbench (a real GPU texture bench: fullscreen quad
whose fragment shader trilinear-samples a mipmapped 1024x1024 texture 2x per pixel across a loop -
combined image sampler, mip chain, LINEAR/LINEAR/REPEAT sampler, descriptor set), the first
texture-path bench in the suite (membench is CPU DDR only). Measured 1920x1080, GPU pinned, v5 vs
the bind-mounted stock blob:
- Turnip v5:  1.48 Gtexels/s (0.720s)
- stock blob: 1.35 Gtexels/s (0.786s)
So Turnip is +9.6% FASTER than stock on trilinear texture sampling. Texturing is NOT our weakness -
we lead stock there. That rules texturing out as the cause of the Wild Life deficit; the WL gap
must be elsewhere in the full-scene pipeline (GMEM tile store/load for the 1440p target, geometry/
overdraw, render-pass mix) - and note UBWC-on (framebuffer compression) made WL worse not better
last tick, so it is not framebuffer UBWC either. The remaining WL gap is a sum of small full-scene
pipeline differences, not a single addressable lever.

Added texbench as a permanent diagnostic (enables future texture-LOD / filtering experiments). No
driver change; device on ULTRA-v5 (16338864). Positive: our texture path already beats the
proprietary blob.

## Texture LOD-bias lever characterized (quality-lossy, no free tier): not a default

Used the new texbench (added a mipLodBias arg) to characterize the "texture LOD bias" candidate
lever - forcing a positive LOD bias samples smaller mips, cutting texture bandwidth. Swept bias on
the deployed v5, 1920x1080:
- bias 0.0: 1.43 Gtexels/s
- bias 0.5: 1.33  (noise / no gain)
- bias 1.0: 1.40  (no gain)
- bias 2.0: 2.35  (+64%)
- bias 4.0: 3.89  (+172%)

The speedup only appears at bias >= 2, where the sampled mips get small enough to fit the texture
cache and stop hitting DRAM. But bias +2 and beyond is VISIBLY blurry (sampling mip 2+), so the
throughput win is purely a quality tradeoff, and crucially there is NO free tier: +0.5 and +1.0
give zero speedup (still DRAM-bound), so no lossless FPS is available from LOD bias.

Conclusion: LOD bias is a real texture-bandwidth performance lever but only at a visible quality
cost, and it is a per-sampler user/emulator preference (a global driver force would blur UI text
and every surface), not a driver default. Not shipping it as a GAMMA lever. This also reconfirms
last tick's finding: our texture sampling is already fast (we lead stock), and the only way to go
faster is to sample less data (blur), not a codegen/sampler-efficiency win. Kept the texbench
lodbias arg for future characterization. No driver change; device on ULTRA-v5 (16338864).

## Periodic 3DMark validation of deployed v5 (4 ticks since last flash): stable, WL 650 / WLE 179

Mandated periodic real-title validation of the shipped ULTRA-v5 driver (16338864), GPU pinned,
both screenshot-verified rendering clean (no black textures, all surfaces textured):
- Wild Life:         650 (3.89 fps)   [baseline 650, exact]
- Wild Life Extreme: 179 (1.07 fps)   [baseline 179, exact]
Shell suite also stable: gpubench 55.4, gamebench 14.0, gfxbench 60.2, vertbench 23.2, rtbench
5508. The deployed driver is confirmed stable and correct across the 4 ticks since the last flash;
no regression.

Side probe (inconclusive): tried GAMMA_UBWC=1 on texbench and it measured slower (0.70 vs 1.46
Gtex/s), but this is a CONFOUNDED result - texbench's source texture has undefined contents, so
its UBWC compression state is invalid and sampling UBWC-flagged-but-uncompressed memory is not a
valid measure of UBWC's effect on real (properly uploaded/compressed) textures. Noting it as
inconclusive rather than a finding; a valid test would need a staging-buffer upload with a UBWC
resolve, out of scope for the microbench. Device stays on ULTRA-v5.
