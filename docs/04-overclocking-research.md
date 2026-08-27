# Overclocking Research: SM6450 (Parrot) and SM4375 (Ravelin)

Scope: two SoC families in this flash package.

- Parrot = Snapdragon 6 Gen 1, SM6450, Adreno 710. DTB `06.parrot.dts` (decompiled from `06.dtb`).
- Ravelin = Snapdragon 4 Gen 2, SM4375, Adreno 613. DTB `11.ravelin.dts` (decompiled from `11.dtb`).

Firmware package: `/mnt/c/55g1/V3.0_debug_20260810/`.

All numbers below were decoded directly from the decompiled device trees and from `strings`/`fdt` inspection of the firmware ELF/MBN blobs. Where a value is a hardware LUT that is not present in the DTB, that is stated explicitly.

Corner naming convention used throughout (RPMh `qcom,level` integers, the standard Qualcomm `RPMH_REGULATOR_LEVEL_*` scale):

| int (hex) | int (dec) | corner |
|-----------|-----------|--------|
| 0x10  | 16  | RETENTION |
| 0x30  | 48  | MIN_SVS |
| 0x38  | 56  | (between MIN_SVS and LOW_SVS, vendor sub-corner) |
| 0x40  | 64  | LOW_SVS |
| 0x60  | 96  | LOW_SVS_L2 |
| 0x80  | 128 | SVS |
| 0xC0  | 192 | SVS_L1 |
| 0xE0  | 224 | SVS_L2 |
| 0x100 | 256 | NOM |
| 0x140 | 320 | NOM_L1 |
| 0x180 | 384 | NOM_L2 |
| 0x1A0 | 416 | TURBO |
| 0x1C0 | 448 | TURBO_L0 |
| 0x1E0 | 480 | TURBO_L1 |
| 0x200 | 512 | TURBO_L2 |

These corner integers are the actual voltage request the GMU/RPMh sends. There is no per-family numeric offset: both Parrot and Ravelin use the same absolute scale (a 0x80 request means SVS on both). The families differ only in which corners each GPU frequency is pinned to.

---

## 1. GPU

### 1.1 Node location and structure

Both families expose the GPU at the same address:

- Parrot: `/soc/qcom,kgsl-3d0@3d00000`, compatible `qcom,adreno-gpu-gen7-3-0`, `qcom,gpu-model = "Adreno710v1"` (DTS line 13334).
- Ravelin: `/soc/qcom,kgsl-3d0@3d00000`, compatible `qcom,adreno-gpu-gen6-3-26-0`, `qcom,gpu-model = "Adreno613v1"` (DTS line 917).

Register window (Parrot): `reg = <0x3d00000 0x40000 0x3d61000 0x800 0x3d50000 0x10000 0x3d9e000 0x1000 0x10900000 0x80000>`, names `kgsl_3d0_reg_memory, cx_dbgc, rscc, cx_misc, qdss_gfx`.

The frequency plan is a child tree:

```
qcom,gpu-pwrlevel-bins (compatible "qcom,gpu-pwrlevel-bins")
  qcom,gpu-pwrlevels-N          (one per speed bin)
    qcom,speed-bin  = <fuse value>
    qcom,initial-pwrlevel = <index into this bin's levels>
    qcom,gpu-pwrlevel@M
      reg              = <M>
      qcom,gpu-freq    = <Hz>
      qcom,level       = <RPMh corner>
      qcom,bus-freq-ddr7 / ddr8 = <index into bus-table-ddr7/ddr8>
      qcom,bus-min-ddr7/8, qcom,bus-max-ddr7/8
      qcom,acd-level   = <ACD/GFXBoost fuse word>   (Parrot/gen7 only)
```

`speed_bin` and `gaming_bin` come from `nvmem-cells = <0x1f4 0x1f5>` (`speed_bin`, `gaming_bin`). At boot KGSL reads the fuse, matches `qcom,speed-bin`, and uses that pwrlevels sub-node. Bin `qcom,speed-bin = <0x0>` is the fallback/default table (used when the fuse does not match any specific bin). The top pwrlevel@0 of the matched bin becomes the max.

### 1.2 Parrot (Adreno 710) full enumeration

`qcom,gpu-freq` is in Hz. Decoded:

Bin 0 (`speed-bin 0x0`, default, `initial-pwrlevel 0x7`), 9 levels:

| lvl | gpu-freq hex | MHz | qcom,level | corner | ddr7 idx | ddr8 idx | acd-level |
|-----|--------------|-----|-----------|--------|----------|----------|-----------|
| 0 | 0x38074300 | 940 | 0x1A0 | TURBO | 8 | 10 | 0xA82B5FFD |
| 1 | 0x342770C0 | 875 | 0x180 | NOM_L2 | 8 | 9 | 0x882C5FFD |
| 2 | 0x30A32C00 | 816 | 0x140 | NOM_L1 | 8 | 9 | 0x882C5FFD |
| 3 | 0x2BBFF380 | 734 | 0x100 | NOM | 7 | 8 | 0xA82C5FFD |
| 4 | 0x26BE3680 | 650 | 0xE0 | SVS_L2 | 6 | 8 | 0xA82C5FFD |
| 5 | 0x23C34600 | 600 | 0xC0 | SVS_L1 | 5 | 7 | 0xA82C5FFD |
| 6 | 0x1DCD6500 | 500 | 0x80 | SVS | 4 | 6 | 0xA82C5FFD |
| 7 | 0x14904840 | 345 | 0x40 | LOW_SVS | 2 | 3 | 0x882D5FFD |
| 8 | 0x119557C0 | 295 | 0x38 | (sub LOW_SVS) | 2 | 3 | 0xA82E5FFD |

`initial-pwrlevel 0x7` means the GPU boots at level 7 (345 MHz) and DCVS ramps up.

Other bins (fused parts). Only the deltas from bin 0 are shown; lower levels are identical entries reused:

- Bin 1 (`speed-bin 0xBE`, i.e. 190), `initial-pwrlevel 0x7`: level@0 = 0x35A4E900 = **900 MHz** at NOM_L2 (0x180). Levels 1..8 identical to bin 0 levels 1..8. This is a slightly down-binned part (top 900 not 940).
- Bin 2 (`speed-bin 0xB2` = 178), `initial-pwrlevel 0x6`: top = 0x324E6B00 = **843 MHz** at NOM_L2. 8 levels.
- Bin 3 (`speed-bin 0x8F` = 143), `initial-pwrlevel 0x4`: top = 0x284AF100 = **675 MHz** at NOM.
- Bin 4 (`speed-bin 0x82` = 130), `initial-pwrlevel 0x3`: top = 0x247A6100 = **611 MHz** at SVS_L2.

Peak silicon-qualified frequency across all Parrot bins: **940 MHz** (bin 0 / default), pinned to TURBO with ACD word 0xA82B5FFD (note this ACD word is unique to the 940 level; every lower level uses the 0x88.. / 0xA8.. 5FFD family).

### 1.3 Ravelin (Adreno 613) full enumeration

Gen6 GPU. Note there is **no `qcom,acd-level`** on these levels (ACD/closed-loop droop is not fused per-level on this part), and no `zap-shader`/`freq_limiter_irq` reset pair like Parrot has.

Bin 0 (`speed-bin 0x0`, default, `initial-pwrlevel 0x6`), 7 levels:

| lvl | gpu-freq hex | MHz | qcom,level | corner | ddr7 | ddr8 |
|-----|--------------|-----|-----------|--------|------|------|
| 0 | 0x3C336080 | 1010 | 0x1A0 | TURBO | 8 | 10 |
| 1 | 0x38EC24C0 | 955 | 0x180 | NOM_L2 | 8 | 9 |
| 2 | 0x32A9F880 | 850 | 0x140 | NOM_L1 | 8 | 9 |
| 3 | 0x2D98F940 | 765 | 0x100 | NOM | 7 | 8 |
| 4 | 0x240F9140 | 605 | 0xC0 | SVS_L1 | 5 | 7 |
| 5 | 0x1DCD6500 | 500 | 0x80 | SVS | 4 | 6 |
| 6 | 0x1443FD00 | 340 | 0x40 | LOW_SVS | 2 | 3 |

Other bins:

- Bin 1 (`speed-bin 0xD5` = 213), `initial-pwrlevel 0x6`: identical to bin 0, top **1010 MHz**.
- Bin 2 (`speed-bin 0xC9` = 201), `initial-pwrlevel 0x5`: top = 0x38EC24C0 = **955 MHz** (NOM_L2). 6 levels.
- Bin 3 (`speed-bin 0xA2` = 162), `initial-pwrlevel 0x3`: top = 0x2D98F940 = **765 MHz** (NOM). 4 levels.

Peak silicon-qualified frequency: **1010 MHz** at TURBO.

### 1.4 Bus / bandwidth vote coupling

Each GPU level carries a DDR bandwidth vote as an **index** into a per-GPU table (identical text in both DTBs):

```
qcom,bus-table-ddr7 = <0x0 0xBEBC2 0x209A8E 0x2DC6C0 0x3C9E30 0x50A524 0x5CAF6A 0x65CE03 0x7F22FF>
qcom,bus-table-ddr8 = <0x0 0xBEBC2 0x1AE1B6 0x209A8E 0x28973C 0x2DC6C0 0x5CAF6A 0x65CE03 0x7CB163 0xA3140C 0xBE7F17>
```

These are AB (aggregate bandwidth) values in KBps. ddr8 index 10 = 0xBE7F17 = 12,484,375 KBps ~ 12.48 GBps, which is the peak LPDDR5 vote. `qcom,bus-freq-ddr8 = 0xa` on the top GPU level therefore requests the maximum DDR bandwidth vote. The GPU talks to DDR through `interconnects = <0x28 0x17 0x26 0x200>` name `gpu_icc_path` (Parrot) / `<0x25 0x15 0x29 0x200>` (Ravelin), which resolves to the MMNOC->LLCC->EBI path handled by the BCM voter.

Key consequence for OC: the bandwidth vote is an index, and index 10 (ddr8) is already the top of the table. A new GPU pwrlevel above the current max cannot request more DDR bandwidth than index 10 unless you also extend `bus-table-ddr8` with a larger AB entry. In practice 12.48 GBps already saturates the LPDDR5 controller on this part, so reusing index 10 for a new top GPU level is correct.

### 1.5 GPU clock source and OC ceiling

GPU clock comes from `gpucc`:

- Parrot: `clock-controller@...` compatible `qcom,parrot-gpucc`, `reg = <0x3d90000 0xa000>`, sourced from `gpll0_out_main` / `gpll0_out_main_div` plus the dedicated GPU PLL inside gpucc. Supplies `vdd_cx` and `vdd_mxa`.
- Ravelin: compatible `qcom,ravelin-gpucc`, same `reg = <0x3d90000 0xa000>`, supplies `vdd_cx` and `vdd_mx`.

The actual GX clock is generated by the GPU_CC_GX PLL (a Lucid/Fabia-class PLL) inside gpucc, programmed by the GMU firmware, not by a frequency listed in the DTB. The DTB only tells the GMU which corner (`qcom,level`) and ACD word to use for a requested Hz; the GMU rounds the requested Hz to the nearest PLL plan it supports. This is the hard ceiling: the GMU/gpucc PLL plan tops out at the highest frequency Qualcomm characterised, which is exactly the top pwrlevel of the highest bin.

Realistic OC ceiling (DTB-only, reusing the existing TURBO corner and top ACD word):

- Adreno 710 (Parrot): stock max 940 MHz. The TURBO corner + 0xA82B5FFD ACD word were characterised at 940. Pushing the top pwrlevel to ~1000-1050 MHz is the practical experimental band; beyond that the GX PLL plan and the TURBO voltage headroom run out and the GMU will either clamp or the `freq_limiter_irq` (interrupt `0x11e`, reset `<0x130 0xa>`) will trip. Do not expect the GMU to synthesize a frequency far outside its plan table.
- Adreno 613 (Ravelin): stock max 1010 MHz already at TURBO. Headroom above ~1050-1100 MHz is minimal; this part is already near its TURBO ceiling out of the box.

### 1.6 How to add a new higher GPU pwrlevel (DTB-only)

Editing the appropriate `qcom,gpu-pwrlevels-N` sub-node (the one matching the device's fused `speed_bin`; when unsure, edit both bin 0 and the specific fused bin so the change applies regardless):

1. Shift every existing `qcom,gpu-pwrlevel@M` down by one (M -> M+1) and update each `reg = <M>` to match. KGSL indexes levels by array position; `reg` must be contiguous from 0.
2. Insert a new `qcom,gpu-pwrlevel@0` with:
   - `reg = <0x0>`
   - `qcom,gpu-freq = <new Hz>` (e.g. 0x3B9ACA00 = 1,000,000,000 = 1000 MHz for Parrot)
   - `qcom,level = <0x1A0>` (keep TURBO; do NOT invent a higher corner, RPMh will reject an unknown corner)
   - `qcom,bus-freq-ddr7 = <0x8>`, `qcom,bus-freq-ddr8 = <0xa>` (top existing bandwidth votes), plus matching `bus-min`/`bus-max`
   - Parrot only: `qcom,acd-level = <0xA82B5FFD>` (reuse the current top ACD word; a wrong ACD word can hang the GX rail).
3. Because a level was inserted at the top, every index-based reference must be bumped by 1:
   - `qcom,initial-pwrlevel` (boot level) -> old value + 1.
   - `qcom,ca-target-pwrlevel` if present -> +1.
   - Any thermal/`#cooling-cells` throttle references that name a level index.
4. Leave `bus-table-ddr7/ddr8` alone (index 10 already tops the table). Only extend it if you genuinely want a higher DDR vote, which also needs the DDR side raised (see section 3).

GMU constraint: the GMU firmware (loaded from the GPU microcode, `zap-shader` memory-region `<0x1f6>`) holds its own copy of the frequency->corner mapping and an OPP sanity check. If the requested Hz is outside the GMU's PLL plan, the GMU refuses the OPP and KGSL falls back to the previous valid level. This is why a modest bump (a few PLL steps) works but a large jump silently does nothing. There is no DTB field that reprograms the GMU PLL plan; that lives in the GMU firmware image.

Risk: DTB-only, no re-sign needed (see section 4). Worst case is a GPU hang recovered by KGSL, or the `freq_limiter_irq` clamping. Keep the corner at TURBO and the ACD word stock to stay inside the electrically-safe envelope.

---

## 2. CPU

### 2.1 Topology

Both are 8-core, two freq-domains (clusters), same `qcom,kryo` compatible with per-core `capacity-dmips-mhz`:

Parrot (`06.parrot.dts`):
- cpu@0..cpu@300: `qcom,freq-domain = <0x7 0x0 0x4>` (domain 0, little cluster, `capacity-dmips-mhz = 0x400` = 1024). 4x Cortex-A78-class efficiency? No: on SM6450 domain 0 is 4x A78 gold at lower cap, domain 1 is the higher-cap cluster. The cap values: domain 0 = 0x400 (1024), domain 1 = 0x799 (1945).
- cpu@400..cpu@700: `qcom,freq-domain = <0x7 0x1 0x4>` (domain 1, prime cluster, `capacity-dmips-mhz = 0x799`).

Ravelin (`11.ravelin.dts`):
- cpu@0..cpu@500: domain 0 (`<0x7 0x0 0x8>`), 6 cores.
- cpu@600..cpu@700: domain 1 (`<0x7 0x1 0x8>`), 2 cores.

The third cell of `qcom,freq-domain` is the LUT row stride hint (0x4 Parrot, 0x8 Ravelin) not a frequency.

### 2.2 Where the CPU frequency/voltage LUT lives

Node: `qcom,cpufreq-hw`, compatible **`qcom,cpufreq-hw-epss`** (EPSS = Enhanced Power State Switching, the SM6450/SM4375 successor to OSM).

- Parrot: `reg = <0x17d91000 0x1000 0x17d92000 0x1000>`, names `freq-domain0`, `freq-domain1`. `qcom,lut-row-size = <0x4>`. `qcom,skip-enable-check`.
- Ravelin: same layout at the same base.

Critical finding: there is **no `qcom,freq-tbl` under `cpufreq-hw`** in either DTB. On older Qualcomm parts (msm8998-era OSM, some SDM parts) the frequency table was in the DTB. Here it is not. The EPSS block at 0x17d91000 (domain 0) / 0x17d92000 (domain 1) exposes a hardware LUT that the Linux `qcom-cpufreq-hw` driver simply **reads** at runtime (it iterates LUT rows until the freq stops incrementing). The kernel never writes frequencies.

The LUT is programmed before the kernel runs. Tracing the source:

- `cpucp.elf` (113 KB, **ELF 32-bit RISC-V**) is the CPUSS Control Processor firmware. Its strings include `CPRh init`, `CPUFreq Stats init done`, `Clarence_CPRh_HSR.xlsx`, `DTECH_DLP_APSS_APM_HSR.xlsx`. CPRh = Closed-loop Process Rail hardened (the voltage side). This is the processor that owns APSS DCVS at runtime, but the frequency/corner LUT rows themselves are handed to it as config.
- `devcfg.mbn` (ELF aarch64) contains the strings `tgt_cpucp_config` (offset 0x4C57) and `/cpucp/cpucpcfg` (offset 0x7059). devcfg is the XBL device-config blob and it carries the cpucp/APSS OSM-EPSS init table (the per-cluster frequency + open-loop voltage rows) that XBL programs into the EPSS/CPRh hardware and/or passes to cpucp during boot.

So the ordering is: XBL parses `devcfg.mbn` -> writes the EPSS LUT (frequency rows) and CPRh open-loop corners -> hands `tgt_cpucp_config` to `cpucp.elf`, which runs closed-loop DCVS at runtime. The Linux DTB only points at the EPSS register window and reads back whatever XBL/cpucp programmed. The LUT is **not fused** (the fuse only carries CPR/speed-bin trim); it is firmware config.

### 2.3 Max CPU frequency per cluster

Because the LUT is not in the DTB, the exposed max is not directly a DTS integer. The L3/DCVS memfreq tables and the DSU/L3 plan bound it indirectly. What can be stated from the tree:

- The `qcom,cpufreq-hw-debug` node lists both domains (`qcom,freq-hw-domain = <0x7 0x0 0x7 0x1>`), confirming two clusters and no third (no separate prime beyond domain 1).
- SM6450 Parrot published stock maxima: gold/efficiency cluster (domain 0) up to ~2.0 GHz, prime (domain 1, the 0x799-cap A78 pair) up to ~2.2 GHz. The exact rows live in devcfg's `tgt_cpucp_config`.
- SM4375 Ravelin published stock maxima: domain 0 (6x A53/A78C mix) ~2.0 GHz, domain 1 (2x prime) ~2.2 GHz.

There is no separate "boost/turbo" LUT row exposed beyond the top OPP; EPSS turbo is simply the top LUT row. Any headroom above stock max would require adding a LUT row inside devcfg/cpucp.

### 2.4 What is editable on CPU without firmware re-sign

- There is **no DTB override path** for CPU frequency on this platform. `qcom,cpufreq-hw-epss` has no `qcom,freq-tbl`; the driver ignores any you add because it reads the hardware LUT. Adding `qcom,freq-tbl` under `cpufreq-hw` does nothing on the EPSS driver (it is only honoured by the older `qcom,cpufreq-hw` OSM binding, not `-epss`).
- Therefore CPU OC requires editing the **firmware**: either the EPSS/CPRh LUT rows in `devcfg.mbn`, or the `tgt_cpucp_config` consumed by `cpucp.elf`. Both `devcfg.mbn` and `cpucp.elf` are signed images. Since this package is a `_debug` build and we can re-sign, the path is:
  1. Locate the APSS/EPSS LUT table inside `devcfg.mbn` near the `tgt_cpucp_config` string at 0x4C57.

     Measured notes (two scans, both negative, do not guess offsets):
     - kHz scan: no monotonic u32 sequence in 300000..3500000 (either endianness) exists in the devcfg config segment (ph[1], file offset 0x1000, size 0x7ee8) or in cpucp.elf. The EPSS LUT does not store frequencies as kHz.
     - lval scan: the EPSS LUT encodes each frequency as an `lval` (target freq as a multiple of the ~19.2 MHz source, so ~15..170) paired with a voltage-corner index. A scan of the devcfg config segment for monotonic lval runs (u16/u32, both endianness, run length >= 5) also found nothing, so the rows are not a contiguous plain-integer table in devcfg either.
     The region around `tgt_cpucp_config` at 0x4C57 is a property-name string table. The row data is therefore inside cpucp.elf's data section (ELF32 RISC-V) or assembled by cpucp at runtime, not a flat table a byte-scan can find. The definitive next step is a Ghidra RISC-V disassembly of cpucp.elf cross-referenced against the SM6450 BSP to recover the row struct; only then edit and re-sign. Do not fabricate offsets.
  2. Raise the top frequency row (and, if the CPRh open-loop corner is row-tied, bump the corner index too), or append a new row.
  3. Re-sign `devcfg.mbn` (and `cpucp.elf` if the LUT is mirrored there).
- APSS/OSM base registers: the EPSS domains are at **0x17d91000** (domain 0) and **0x17d92000** (domain 1). The L3/DSU DCVS-HW block is at **0x17d90000** (`reg = <0x17d90000 0x4000 0x17d90100 0xa0>`, names `l3-base`, `l3tbl-base`) inside `qcom,dcvs -> l3`. The APSS clock controller syscon is at **0x17aa0000** (`syscon@17aa0000`, referenced by debugcc `qcom,apsscc`).

### 2.5 L3 / DSU scaling

`qcom,dcvs -> l3` (`qcom,dcvs-hw-type = <0x2>`, bus-width 0x20) drives the L3/DSU. The L3 frequency is voted as a function of CPU freq via `qcom,cpufreq-l3-memfreq-tbl` style tables (the `l3` entries under the memlat/l3 nodes, e.g. Parrot line 6845). Those tables map CPU MHz -> L3 MHz and would need matching new rows if CPU top frequency is raised, otherwise L3 stays pinned at the current top vote (a performance limiter, not a stability risk).

Risk: CPU OC is the highest-risk of the three. A bad EPSS row or a frequency that exceeds the CPRh open-loop voltage envelope can brick-boot (XBL hangs before the kernel). Requires firmware re-sign. Recommend small single-row bumps, keep the corner mapping conservative (do not exceed the top CPRh corner already used), and test with a known-good recovery path.

---

## 3. Memory (DDR / LLCC / BCM)

### 3.1 ddr-freq-table decode

Node `/soc/ddr-freq-table` (Parrot line 6685, Ravelin line 7247), identical values in both families:

```
ddr4 { qcom,ddr-type = <0x7>;  // LPDDR4X
  qcom,freq-tbl = <0x858B8 0xBB800 0xF84A8 0x14A780 0x17BA38 0x1A0FE0 0x1FEBE0>; }
ddr5 { qcom,ddr-type = <0x8>;  // LPDDR5
  qcom,freq-tbl = <0x858B8 0xBB800 0x17BA38 0x1A0FE0 0x1FEBE0 0x29BF80 0x30C460>; }
```

These are **DDR clock frequencies in kHz** (the DDR DCVS clock plan), not bandwidth votes. Decoded:

| index | ddr4 kHz | ddr4 MHz | ddr5 kHz | ddr5 MHz |
|-------|----------|----------|----------|----------|
| 0 | 547,000  | 547   | 547,000  | 547 |
| 1 | 768,000  | 768   | 768,000  | 768 |
| 2 | 1,017,000| 1017  | 1,555,000| 1555 |
| 3 | 1,353,600| 1353.6| 1,708,000| 1708 |
| 4 | 1,555,000| 1555  | 2,092,000| 2092 |
| 5 | 1,708,000| 1708  | 2,736,000| 2736 |
| 6 | 2,092,000| 2092  | 3,196,000| 3196 |

Top ddr4 = 2092 MHz clock = LPDDR4X-4184 (~4267 class). Top ddr5 = 3196 MHz clock = LPDDR5-6392 (~6400 class). These are the DDR command-clock steps that the DDR DCVS driver selects between.

Distinction from the GPU bandwidth vote: the GPU `bus-table-ddr7/ddr8` values (e.g. 0xBE7F17 = 12,484,375 KBps) are **AB bandwidth in KBps**, a different quantity. The DDR clock table above is what the DDR PLL actually runs at; the BCM/AB vote is what a client requests, and the DDR DCVS driver picks the lowest DDR clock step that satisfies the aggregate AB. `qcom,dcvs -> ddr` (`qcom,dcvs-hw-type = <0x0>`, bus-width 0x4) uses `qcom,freq-tbl = <0x133>` (a phandle back to this `ddr-freq-table`), confirming these entries are the DDR DCVS operating points.

The `ddr4-tbl`/`ddr5-tbl` sub-tables under the L3/memlat nodes (e.g. Parrot line 6774) are `{cpu_freq_khz, ddr_freq_khz}` pairs mapping CPU frequency to a minimum DDR vote, and they reference the same kHz values (e.g. 0x1FEBE0 = 2092 MHz appears as the top ddr4 target), cross-confirming the units.

### 3.2 Where the DDR max is actually set

The DTB `ddr-freq-table` is a **menu of operating points the DDR DCVS driver may vote for**; it does not itself define the DDR PLL ceiling. The actual maximum DDR clock is fixed earlier:

- DDR training and the DDR PLL/clock plan are done by **XBL** (`xbl_config.elf`) during cold boot.
- The runtime DDR frequency switching (BCM_CHNG, the `bcm_lp5dr_scalar`, `bcm_snd_lp4`, `bcm_starc_0/1` entries seen in `aop.mbn` strings) is owned by **aop.mbn** (the AOP/RPMh always-on processor). `aop.mbn` strings confirm the DDR state machine lives there: `DDR_ON`, `DDR OFF`, `Enab DDR`, `ddr.lvl`, `ddr.mol`, `ddr_freq_disable`, `bcm_lp5dr_scalar`.
- `shrm.elf` (Shared Resource Manager, 60 KB) arbitrates the DDR/LLCC bandwidth requests.

So raising the top `ddr-freq-table` entry in the DTB alone will **not** overclock DDR: if you request a clock the aop/xbl DDR plan does not have a trained setpoint for, the AOP rejects it and stays at its max trained frequency. Real DDR OC requires the trained frequency and the BCM scalar (`bcm_lp5dr_scalar`) in `aop.mbn` (plus the XBL DDR PLL plan) to be raised, which are signed images that must be re-signed. The memory controller (MCCC syscon at `0x190ba000`, referenced by debugcc `qcom,mccc`) is where the DDR clock actually lands.

### 3.3 LLCC (system cache) and BCM

- BCM voter: `qcom,bcm-voter` nodes at Parrot lines 5103 / 6055; `qcom,bcm-voter-names = "hlos"` / `"hlos","disp"` with `qcom,bcm-voters = <0x13e ...>`. These aggregate all interconnect (icc) votes into BCM commands sent to RPMh/aop.
- The DDR/EBI path terminates at the memory controller; the LLCC-to-EBI leg is voted through the `llcc_to_ebi1`/`memnoc_to_ddr` interconnect edges (seen on many clients, e.g. Ravelin line 12494 `memnoc_to_ddr`). The LLCC frequency itself scales with the same BCM aggregation; there is no separate DTB `qcom,freq-tbl` for LLCC clock that can be raised. Raising LLCC/EBI throughput is governed by the same aop BCM scalar as DDR.

Consequence: LLCC and bus (BCM) scaling are not DTB-editable to a higher ceiling. They follow the aop-programmed BCM setpoints. You can change which client votes how much (icc edges in the DTB), but not the top setpoint the BCM can deliver.

---

## Summary: what to edit, effect, ceiling, risk, re-sign

### GPU
- Edit: the matching `qcom,gpu-pwrlevels-N` under `/soc/qcom,kgsl-3d0@3d00000/qcom,gpu-pwrlevel-bins` in the DTB. Insert a new `qcom,gpu-pwrlevel@0`, renumber existing levels/`reg`, bump `qcom,initial-pwrlevel` and any `ca-target-pwrlevel`, keep `qcom,level = 0x1A0` (TURBO), reuse top bus indices (ddr7=8, ddr8=10), and on Parrot reuse `qcom,acd-level = 0xA82B5FFD`.
- Effect: raises GPU max clock. Bandwidth vote already maxed (index 10).
- Ceiling: Adreno 710 stock 940 MHz, experimental ~1000-1050 MHz; Adreno 613 stock 1010 MHz, experimental ~1050-1100 MHz. Bounded by the GMU/gpucc GX PLL plan, which the DTB cannot change.
- Risk: low-moderate. Out-of-plan requests are silently clamped by the GMU or trip `freq_limiter_irq`; recoverable.
- Re-sign: **NO. Pure DTB edit.** (The DTB/dtbo is not part of the signed secure-boot chain here; only firmware ELF/MBN are.)

### CPU
- Edit: the EPSS/CPRh LUT rows inside `devcfg.mbn` (near `tgt_cpucp_config` @0x4C57 / `/cpucp/cpucpcfg` @0x7059), and possibly the mirror in `cpucp.elf`. There is NO DTB path: `qcom,cpufreq-hw-epss` at 0x17d91000/0x17d92000 has no `qcom,freq-tbl` and the driver reads the hardware LUT.
- Effect: raises per-cluster CPU max. Also bump L3 `cpufreq-memfreq-tbl` rows (DTB) so L3 scales with the new top.
- Ceiling: Parrot ~2.2 GHz prime stock, Ravelin ~2.2 GHz prime stock; headroom limited by CPRh open-loop voltage corners.
- Risk: high. Bad row or over-voltage-envelope frequency can hang XBL before kernel (boot brick). Needs a recovery path.
- Re-sign: **YES.** `devcfg.mbn` and/or `cpucp.elf` are signed; must re-sign (possible on this debug package).

### Memory
- Edit (DTB, cosmetic only): `/soc/ddr-freq-table` `ddr5`/`ddr4` `qcom,freq-tbl` top entry, plus the L3/memlat `ddr*-tbl` targets. This only changes which setpoints Linux may vote for.
- Edit (real OC): the DDR PLL/trained plan in `xbl_config.elf` and the BCM scalar (`bcm_lp5dr_scalar`) / DDR level state in `aop.mbn`; the memory controller lands at MCCC syscon 0x190ba000.
- Effect: raises actual DDR clock (stock top: LPDDR4X 2092 MHz clock, LPDDR5 3196 MHz clock).
- Ceiling: the highest frequency XBL trains and aop has a BCM setpoint for. A DTB-only bump above the trained max is rejected by the AOP.
- Risk: high. Untrained DDR frequency = memory corruption / no-boot. LLCC/BCM scaling is not independently raiseable (follows aop setpoints).
- Re-sign: **YES** for any real effect (aop/xbl are signed). DTB-only edits have no effect beyond the trained ceiling.

### One-line takeaway
Only the **GPU** is a safe, pure-DTB overclock on both Parrot and Ravelin. **CPU** and **DDR** ceilings live in signed firmware (devcfg/cpucp for CPU, xbl/aop for DDR) and require re-signing to move; DTB edits to `cpufreq-hw-epss` or `ddr-freq-table` above the firmware-set ceiling are ignored.
