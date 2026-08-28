# Overclock stress-test and benchmark campaign (RG 55G1 / RavelinP)

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
