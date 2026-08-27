# cpucp.elf (SM6450 Parrot) RISC-V reverse engineering: where is the CPU freq/voltage LUT?

Target: `/work/sd-tools/stock/firmware/cpucp.elf`
SoC: SM6450 "Parrot" (Snapdragon 6 Gen 1). ELF32 little-endian RISC-V (RVC), entry 0x90.

Bottom line up front: the EPSS/OSM CPU frequency/voltage operating-point LUT is NOT
stored in cpucp.elf, and cpucp does not program or read it. cpucp is the DCVS
controller: it issues perf-level requests and reads status via a small set of EPSS
domain control/status registers, but it never touches the FREQ_LUT register window and
carries no lval source array. Overclocking by editing cpucp.elf is not possible on this
firmware. The LUT lives in the EPSS hardware, programmed by XBL/devcfg (the OSM/EPSS
init blob), which is where the edit must happen. Confidence: high (see evidence).

## Segment / VADDR map (from readelf -l, confirmed)

| PT_LOAD | file off | real VADDR (p_paddr) | filesz  | flags | contents |
|---------|----------|----------------------|---------|-------|----------|
| #1      | 0x001000 | 0x17d00000           | 0x06982 | R+E   | code seg A (in APSS/CPUSS reg space) |
| #2      | 0x008000 | 0x17d08000           | 0x00fe4 | RW    | data |
| #3      | 0x009000 | 0x17d0a000           | 0x0056c | RW    | data |
| #4      | 0x00a000 | 0x17d0b000           | 0x01be8 | RW    | data (driver state structs, `lui 0xb`) |
| #5      | 0x00c000 | 0x80b00000           | 0x05a56 | R+E   | code seg B |
| #6      | 0x012000 | 0x80b10000           | 0x061c4 | RW    | main .data / .rodata (`lui 0x80b1x`) |
| #7      | 0x019000 | 0x80b20000           | 0xa0000 | RW    | .bss (no file bytes) |

Note: p_vaddr in the file is 0 / low for the code segments; the real load address is in
p_paddr. llvm-objdump labels these PT_LOAD#1 (add 0x17d00000) and PT_LOAD#5
(add 0x80b00000). All addresses below are quoted in file-relative form as objdump prints
them for seg A (real = shown + 0x17d00000) and in full VADDR form for seg B.

## Tooling

- Disassembly that actually works: llvm-objdump 18 (NDK r27c) with
  `--triple=riscv32 --mattr=+c,+zicsr,+m,+a,+f`. Plain capstone RISCV32 desyncs on the
  first compressed/unknown halfword and covers almost nothing, so objdump is authoritative
  here; capstone is only used for the register-tracked offset scan.
- Helper: `/work/sd-tools/tools/fw/cpucp_disasm.py` (segment loader at true VADDRs,
  lui/addi/auipc materialization tracker, store-flagging disassembler).
- `/work/sd-tools/tools/fw/scan_freq_tables.py` (heuristic lval/MHz table scanner).

## Device-tree facts used as the search key

- EPSS cpufreq-hw domains: domain0 base 0x17d91000, domain1 base 0x17d92000.
- L3/DSU DCVS-HW: 0x17d90000. APSS syscon: 0x17aa0000.
- An EPSS FREQ_LUT is a per-index register block inside each domain, conventionally at
  domain_base + 0x100 + n*4, each row carrying an lval (= target_freq / 19.2 MHz XO,
  small ints ~15..125) plus a voltage/corner field.

## Evidence 1: the EPSS domain bases are materialized, but only for control regs

Every place the code builds a domain base is a plain `lui` (addi offset 0), so the base is
exactly domain_base + 0x000. Grepping `lui .*0x17d9[012]` finds 33 sites. A
register-tracked scan (track the lui'd register, record the first mem access off it,
stop at register reuse) yields the complete set of offsets cpucp touches off the real
EPSS domain bases:

```
0x17d90 (L3)      +0x000 lw    (enable/CMD status)
0x17d90 (L3)      +0x054 sw    @0x6d2
0x17d90 (L3)      +0x300 lw/sw
0x17d90 (L3)      +0x304 lw/sw (ori 0x8 = a bit-set, @0x80b05262)
0x17d90 (L3)      +0x340 lw/sw @0x2d12 / @0x343c
0x17d90 (L3)      +0x350/354/358/35c sw @0xd66  (4 bytes from cfg struct+0x144)
0x17d90 (L3)      +0x3bc lw    (status poll)
0x17d91 (domain0) +0x000 lw    @0x13b0
0x17d91 (domain0) +0x304 lw/sw @0x80b05274
0x17d91 (domain0) +0x350/354/358/35c sw @0xd90
0x17d92 (domain1) +0x000 lw    @0x148e
0x17d92 (domain1) +0x350/354/358/35c sw @0xdb4
```

Nothing else. In particular a targeted scan for any load or store in the FREQ_LUT window
`0x100 <= off < 0x300` off any of the three real domain bases returns zero hits:

```
=== any offset in 0x100..0x2fc off a 0x17d9 domain reg (FREQ LUT window)? ===
done (no HIT lines above = LUT window never touched)
```

The 0x350..0x35c block (seen at 0xd66/0xd90/0xdb4 for L3/domain0/domain1) copies four
byte-wide fields out of a config struct at struct+0x144 into consecutive domain control
registers. That is DCVS threshold/vote config, not a frequency table (a freq LUT would be
an indexed loop over 0x100+n*4 writing lval words; there is no such loop anywhere in
either code segment). Offsets 0x300/0x304 are enable/CMD bits (read-modify-write with
`ori 0x8`); 0x3bc is a status register polled in loops.

## Evidence 2: no lval source array in .data

A stride/offset sweep of the main .data (0x80b10000, size 0x61c4) for monotone runs of
lval-sized integers (12..125) at 1/2/4-byte widths and strides 1/2/4/8, requiring a top
value >= 90 and a spread >= 20 (so it would have to reach ~2.0/2.2 GHz worth of lval,
~104/115), produced no frequency-table candidate. The only "runs" that matched the numeric
filter decode to ASCII and are the HSR spreadsheet filename strings embedded in the blob:

```
0x80b1616c: "Clarence_CPRh_HSR.xlsx"
0x80b14a94: "...APSS_APM_HSR.xlsx"
```

The seg-A data region (0x17d0b000, `lui 0xb`) holds driver state structs accessed at
offsets like 0xe0/0xec/0x5dc/0x773/0x144, i.e. runtime state and the small DCVS config
struct, not an indexed freq/voltage LUT.

The freq-looking arithmetic at 0x80b035ea (`mul`/`divu` by 0x3e8=1000, `srli 0xc`,
`andi 0x1f`) reads fields at struct+0x7f8 and +0x14 of a chained OPP/stats structure and
computes a display frequency for CPUFreq stats (`"CPUFreq Stats init done"` at 0xb7d4). It
consumes frequencies that already exist in the OPP structures; it is not the source of the
hardware LUT and has no writable lval array behind it.

## Conclusion and where the LUT actually is

cpucp.elf on SM6450 is a pure DCVS engine. It:
- reads the domain enable/status registers (+0x000, +0x3bc, +0x300/0x304),
- writes DCVS vote/threshold config (+0x340, +0x350..0x35c) from a small byte-field
  config struct,
- runs CPUFreq stats and CPRh init (`"CPRh init"` at 0xb754),

and never programs or reads the EPSS FREQ_LUT (domain_base + 0x100 + n*4). Therefore the
frequency/voltage operating points are not in this file and cannot be raised by editing it.

To overclock this SoC the LUT must be edited where it is programmed into EPSS/OSM, which
on Qualcomm EPSS parts is the OSM/EPSS init table inside XBL / devcfg (look for the
per-domain FREQ_LUT and PERF_STATE arrays keyed off 0x17d91000/0x17d92000 in
`devcfg.mbn` or the EPSS init section of `xbl_config.elf`). The lval-to-MHz corroboration
(top lval ~104 -> ~2.0 GHz domain0, ~115 -> ~2.2 GHz domain1) should be applied there,
together with the matching CPRh voltage corner so the raised lval stays inside the voltage
envelope (out-of-envelope lval hangs boot).

## Honesty note

No offset in cpucp.elf is given as an OC edit target because none is defensible: the
required table is absent from the file. This is a negative result, corroborated by (1) the
complete register-offset map showing the FREQ_LUT window is never accessed and (2) the
absence of any lval source array in the data segments. Confidence: high. The remaining
open item is to repeat this analysis on devcfg.mbn / xbl_config.elf, which are the correct
targets and were out of scope for this file.
