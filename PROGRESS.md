# Progress ledger

State of the sd-tools work. Updated as the work advances.

## Done and validated

- SoC identification: package bundles Parrot (SM6450, Adreno 710), Montague and
  Ravelin (SM4375, Adreno 613); selected by msm-id. `docs/03`.
- Signing state: whole boot chain is SecTools test-key signed (ECDSA secp384r1,
  SB3.0), so secure boot is very likely open. `tools/signing/inspect_mbn.py`,
  `docs/01`.
- AOSP dtc built and committed (`prebuilt/dtc-aosp-x86_64`); proven the distro
  dtc mangles `qcom,gpu-freq` into a string. `docs/02`.
- DTB split/join, and `verify_roundtrip.sh` proving SEMANTIC-MATCH + idempotent
  on all 15 trees. `docs/02`.
- abie patch (`patches/abie-use-aosp-dtc.patch`) built and verified end-to-end:
  unpack renders correct integers, full vendor_boot repack re-extracts to 15
  valid FDTs with the edit present.
- GPU overclock: `gpu_overclock.sh` (raise top) and `add_gpu_level.py` (add a new
  top level, renumber, keep default) both validated on Parrot AND Ravelin.
- Firmware re-sign: `resign_firmware.sh` with qtestsign (MBN v6, validated on
  ABL) and a sectools path; supports devcfg/cpucp/aop for the CPU/DDR case.
- End-to-end repack script and 8-check `selftest.sh` (all passing).
- Flashing/recovery guide with the A/B partition map and the EDL programmer
  (`xbl_s_devprg_ns.melf`). `docs/05`.
- Self-contained: stock firmware + trees + certs + test keys committed.

## Iteration notes

- vbmeta.img is signed (RSA4096, enforced); added make_disabled_vbmeta.sh and
  corrected the docs.
- Firmware freq-table scanner (`tools/fw/scan_freq_tables.py`) added. It located
  the AOP DDR/bus clock-plan region (aop.mbn 0x11a90..0x11af0, beside the RPMh
  `ebi.mol`/`ddr.mol` strings). Location corroborated, edit-struct still undecoded.
- CPU LUT byte-scans (kHz + lval) are confirmed dead ends (hits exceed real CPU
  max).
- CPU LUT RISC-V disassembly of cpucp.elf DONE (docs/06): cpucp is a DCVS engine,
  never touches the FREQ_LUT window, holds no lval array. Not the LUT home.
- CPU LUT ARM64 analysis of xbl_s/uefi/devcfg DONE (docs/07): no static editable
  EPSS LUT in the shipped images; the freq plan is inside the compressed XBL
  loader payload and CPRh-composed at runtime. Static-firmware CPU OC not viable
  from these artifacts. Added tools/fw/epss_lut.sh for the live on-device route.
- Verified each cycle: selftest 8/8 green, abie patch applies to a fresh clone.

## Open (needs the device or deep disassembly)

- Fuse-state confirmation (`fastboot oem device-info`). Gates any XBL/devcfg
  flash. Only the physical unit can answer it.
- CPU EPSS LUT: investigation concluded (docs/06 + docs/07). No static editable
  LUT in the shipped images; it is composed at runtime inside the compressed XBL
  loader. Remaining route to a firmware edit is to decompress the xbl_s.melf
  loader payload and edit the freq-plan array, then re-sign; otherwise use the
  live on-device tool (tools/fw/epss_lut.sh). `docs/04`.
- DDR ceiling raise: the DTB `ddr-freq-table` only exposes trained setpoints;
  the real ceiling is in xbl_config/aop and a DTB entry above it is ignored.
  Needs aop/xbl analysis. `docs/04`.
- On-device validation of the GPU overclock (repacked vendor_boot) once the unit
  is available.

## Candidate next work

- Ghidra headless script to locate the cpucp freq/corner LUT.
- avbtool vbmeta regeneration helper for the repacked vendor_boot.
- A single-bin GPU tree fallback in `add_gpu_level.py` (currently multi-bin;
  Parrot and Ravelin are both multi-bin so this is not blocking).
