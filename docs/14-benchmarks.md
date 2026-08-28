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
