# XBL / EPSS FREQ_LUT programming: static-vs-runtime determination (SM6450 Parrot)

Continuation of the cpucp investigation (see 06-cpucp-riscv-lut.md). We proved cpucp.elf is a
DCVS engine, not the OPP source. This document determines where the EPSS FREQ_LUT operating
points come from in the boot chain and whether the source is a statically editable table.

## Bottom line

The EPSS FREQ_LUT is NOT stored as a plaintext, directly-editable operating-point table in any
of the shipped, disassemblable firmware images (xbl_s.melf, uefi.elf, xbl_config.elf, devcfg.mbn).
The XBL Loader payload (xbl_s.melf) and the UEFI XBL Core (uefi.elf) that would contain the
OSM/EPSS clock-driver code that writes domain_base+0x100.. are both COMPRESSED, so the
LUT-writing loop and its source pointer could not be recovered by static disassembly from these
artifacts. The voltage side is corner/CPR driven (evidence below), consistent with a runtime
compose of freq-plan + CPR corner rather than one editable dword table.

Confidence: HIGH on "no editable plaintext EPSS LUT in these images"; MEDIUM on the mechanism
being runtime-composed (strong circumstantial evidence, but the exact writing loop is inside
compressed payloads not extracted here).

## Segment / VADDR map (parsed manually; readelf mis-tags machine type)

xbl_s.melf   ELF32, machine mis-tagged 0x1, entry 0x2211c000
  PT_LOAD ph0 off 0x74     va 0x2211c000 fsz 0x1c000   <- XBL Loader payload (COMPRESSED)
  PT_LOAD ph1 off 0x1c074  va 0x22143000 fsz 0x280
uefi.elf     ELF64, machine 0x28, entry 0xa7000000
  PT_LOAD ph1 off 0x1000   va 0xa7000000 fsz 0x2a0000   <- UEFI Firmware Volume ("_FVH")
                                                           mixed AArch64/THUMB TE modules,
                                                           DXE section LZMA/GUID compressed
xbl_config.elf ELF64, machine mis-tagged 0x1, entry 0x1494e000
  ph1..ph8 va 0x1494e000.. : DALConfig blob (name table + value blobs)
devcfg.mbn   ELF64 AArch64, entry 0x1c003000
  ph1 off 0x1000 va 0x1c003000 fsz 0x7ee8 : DALConfig blob (name table + value blobs)
  ph2 off 0x9000 va 0x805fd000 fsz 0xa00

## Evidence

### EPSS base constants are never present as literals
Raw little-endian dword scan for 0x17d90000 / 0x17d91000 / 0x17d92000 / 0x17aa0000 across all
four files: ZERO hits. On AArch64 these are materialized by adrp+add or movz/movk (constant is
split across instruction encoding fields), so their absence as literals is expected and means the
writing code, if present, is in an executable segment.

### The executable segments that would hold the clock/OSM driver are compressed
- xbl_s.melf ph0 (0x2211c000, 0x1c000 bytes): 0 valid AArch64 and 0 valid AArch32 instructions
  when disassembled at its load VA; ~151 unique bytes per 4KB (high entropy). This is a
  compressed XBL Loader payload. adrp+add scan for any 0x17aa.. / 0x17d9.. base: 0 hits.
- uefi.elf FV: header magic "_FVH" at file start of ph1. Contains ~1 uncompressed TE module
  (AArch64, at seg-offset 0x1f38, ImageBase 0xa7001000, StrippedSize 0xf60) which is the SEC/
  PrePi stub; the remaining 41 "VZ" matches are false positives inside compressed DXE sections.
  adrp+add scan of the flat FV and of the one real TE for EPSS bases: 0 hits. The OSM/ClockApp
  DXE driver lives inside the compressed DXE volume and was not extracted.
- uefi.elf contains NONE of the OSM/CPR/clock strings (see next), confirming EPSS/OSM bring-up is
  an XBL-Loader (xbl_s) responsibility, not UEFI Core.

### The voltage side is corner/CPR driven (runtime), not a fixed mV column
String evidence in xbl_s.melf and xbl_config.elf (absent from uefi.elf and devcfg.mbn):
  /cpr.bin, cx_corner, float-voltage-mv, apply-float-voltage, rail_voltage_levels,
  "/sw/clk_pegging_node : cx_corner[%x]..ddr_min_max[%x]..shub_min_max[%x]", secpro
This is the CPRh / rail-corner path: XBL reads CPR fuse data (/cpr.bin), resolves per-corner
float voltages, and pegs rail corners. The EPSS row voltage/corner field is therefore composed at
runtime from the CPR corner map, not stored as a fixed voltage byte next to a fixed frequency.
This matches the standard Qualcomm OSM/EPSS bring-up (freq plan -> lval; corner -> CPRh envelope).

### devcfg.mbn has no OSM/OPP value table
The strings tgt_cpucp_config (@file 0x4c57), /cpucp/cpucpcfg (@0x705a/0x7060), frequency (@0x58a4,
part of OEM_ese_spi_max_frequency) are all NAME-table entries in the DALConfig string blob, not
data. Their surrounding bytes are adjacent config-key names / GUIDs, not decodable frequency rows.
Monotonic-lval heuristic hits in devcfg (0x1b9f, 0x70db) fall inside the ELF hash/signature blob
and a GUID string respectively (false positives). No EPSS OPP table in devcfg.

### xbl_config.elf: the one large structured numeric table is NOT the EPSS LUT
At file 0x96de there is a large monotonically-increasing array of 16-bit values (12,13..34, 65..92,
108..131, 162.., climbing past 0x037f). Its length (hundreds of entries), 16-bit stride, and range
far beyond the EPSS lval ceiling (~104 for dom0 / ~115 for dom1) rule it out as a per-index EPSS
FREQ_LUT (which is ~16-40 rows). It is a sparse index/plan map, and AArch64 code bytes
(02 ff 80 92 80 93 = "mov x2,#...; movk" fragments) leak into it, i.e. it abuts code, not an OPP set.
The nearby cx_corner / rail_voltage_levels / table tokens are DALConfig key names, not a mV column.

## Why an "editable static LUT" recipe cannot be given from these images

Programming the EPSS FREQ_LUT (domain_base + ~0x100..0x2FC) is done by the OSM/clock driver that
is compressed inside xbl_s.melf (XBL Loader). The driver reads a frequency plan (lval = MHz/19.2)
and, per row, an ACC/CPRh corner index, then writes each row register. The frequency-plan array and
the max-frequency cap are the editable inputs, but they live in the compressed payload (or in a
CPR/plan blob resolved from /cpr.bin + fuses) and are not exposed as plaintext here. There is no
single dword in the shipped, uncompressed data that says "2.0 GHz" (lval 104) or "2.2 GHz"
(lval 115) that can be bumped.

## To actually recover / edit the table, next steps (not doable from current artifacts)

1. Decompress xbl_s.melf ph0. Qualcomm XBL Loader payloads are typically zlib/gzip or a custom
   header. Once decompressed to flat AArch64, re-run tools/fw/xbl_disasm.py against the real base
   to find the adrp/add or movz/movk that materializes 0x17d91000/0x17d92000 and the str/stp loop
   into base+0x100.., then trace the source pointer (rodata plan array vs CPR-derived arithmetic).
2. Extract the UEFI DXE volume (LZMA GUIDed sections) and disassemble the ClockApp/OSM DXE driver
   as a cross-check (though strings indicate OSM is in the Loader, not Core).
3. Read the live EPSS FREQ_LUT from a booted device (devmem2 domain_base+0x100.., domain0
   0x17d91000, domain1 0x17d92000) to confirm the stock rows/corners; that live table is the true
   post-programming state and is the practical target for a runtime overclock (write lval rows) if
   the registers are not locked, sidestepping the need to edit XBL at all.

## Determination

RUNTIME-COMPOSED (freq plan lval + CPRh corner), programmed by the compressed XBL Loader
(xbl_s.melf), with the voltage side driven by /cpr.bin fuse corners. Not a static, plaintext,
byte-editable OPP table in the shipped xbl_s.melf / uefi.elf / xbl_config.elf / devcfg.mbn.
Editable inputs (freq-plan array, max-freq cap, per-corner float mV) exist but are inside the
compressed Loader payload / CPR blob and were not corroborable from these images.

CPRh voltage-envelope risk: raising an lval without moving its bound corner runs the core above
the CPRh voltage envelope for that OPP -> instability/silent-data-corruption. Any overclock must
also raise the corner or accept the higher corner's float voltage.

## Practical route: the live EPSS FREQ_LUT (tools/fw/epss_lut.sh)

Because no static LUT is editable in the shipped images, the concrete CPU-OC
route on a booted, rooted device is to read and (experimentally) write the EPSS
hardware LUT directly. `tools/fw/epss_lut.sh` does this over adb:

```
tools/fw/epss_lut.sh dump 0      # domain0 (efficiency) FREQ+VOLT LUT, decoded to MHz
tools/fw/epss_lut.sh dump 1      # domain1 (prime)
tools/fw/epss_lut.sh write 1 <row> <lval>   # EXPERIMENTAL, root, CPRh-envelope risk
```

Register model (Linux qcom-cpufreq-hw): domain0 base 0x17d91000, domain1
0x17d92000; FREQ_LUT[i] = base + 0x100 + i*4 with lval = reg & 0xFFF and
freq_kHz = lval*19200; VOLT_LUT[i] = base + 0x200 + i*4. Dump is read-only and
safe; writes may be re-latched by the EPSS or ignored, and a frequency above the
CPRh voltage envelope can hang the CPU, so read first and bump conservatively.
This sidesteps editing and re-signing XBL entirely.

## Update: the CPU clock plan is in uefi.elf ClockDxe (decompressed)

Correction and progress on the "compressed loader" note above. xbl_s.melf is only
the ~115KB XBL SEC loader (2 small LOAD segments, ph0 is structured config data
at entropy 5.52, the rest of the file is the MBN hash/cert blob). The CPU clock
bring-up (OSM/APSS) is in uefi.elf, the XBL Core, which is a UEFI firmware volume
(FVH at file 0x1000) whose body is one LZMA-compressed GUIDed section.

`tools/fw/extract_uefi.sh` carves the FV and runs uefi-firmware-parser, which
decompresses the LZMA volume and dumps 553 files. The decompressed content
confirms the CPU clock path:

- CPU clock is the APSS Zonda Evo PLL: strings `APCS_CPU_APCS_CPU_CM_PLL_ZONDA_EVO`,
  `apss_cc_l3_pre_acd_debug_div_clk_src`, `APSS_KRYO_CLK_CTL`, `APSS_ACD`.
- The clock driver is ClockDxe, FFS GUID `4db5dea6-5302-4d1a-8a82-677a683b0d29`
  (extracted `.../file-4db5dea6.../section1.pe`, 172 KB AArch64 PE).

Inside ClockDxe section1.pe the frequency configs are `{UINT64 nFreqHz, UINT32
cfg, ...}` structs (freq in Hz, high dword 0, then a source/div config dword such
as 0x00400280). CPU-range entries found:

| PE offset | freq (MHz) |
|-----------|-----------|
| 0x16950 | 1518 |
| 0x16998 | 1824 |
| 0x182c0 | 1530 |
| 0x18308 | 1700 |
| 0x18350 | 1910 |
| 0x18398 | 2020 |

Status: these are confirmed to be ClockDxe frequency-config entries in the
CPU/L3 range, but which clock domain each belongs to (APSS CPU cluster vs L3 vs a
bus) is not yet confirmed; that needs tracing the parent HAL clock-domain struct
that references the table. Editing a CPU entry means bumping its nFreqHz AND the
PLL L-value/config dword, then re-signing uefi.elf and reflashing the xbl
partition, staying within the CPRh voltage envelope. This is the concrete
static-firmware CPU-OC path; the on-device epss_lut.sh route remains the simpler
alternative. The decompressed tree is regenerable with extract_uefi.sh and is
gitignored to keep the repo small.
