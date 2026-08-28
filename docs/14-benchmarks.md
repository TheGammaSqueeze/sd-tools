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
| baseline | 1010 | 2400 | 129.2 | 298.2 | 37.8 | 38 C | yes (stock) |
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
That rules out simple GX rail voltage as the limiter and points at the **GMU ACD**
(the GMU firmware does closed-loop adaptive clock distribution with per-OPP
calibration; frequencies above the stock 1010 have no ACD data). A stable GPU OC
therefore needs `a650_gmu.bin` ACD-table work, not just the clock table or an
RPMh corner bump. **Stable GPU ceiling on this unit: 1010.** The DTB voltage-corner
lever is `qcom,gpu-pwrlevel@0 { qcom,level }` (0x1a0=TURBO_L1 .. 0x1e0=TURBO_L3).

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
