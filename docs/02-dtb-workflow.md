# Qualcomm device tree workflow

## Why the distro dtc is wrong here

Qualcomm device trees must be decompiled and recompiled with the **AOSP/Android
dtc**, not the distro `dtc` (1.6.x on most Linux). The concrete failures of the
distro dtc on these trees:

- It renders a 4-byte integer property whose bytes are printable as an escaped
  string. The top GPU frequency is the clearest example:
  - distro dtc:  `qcom,gpu-freq = "8\aC";`
  - AOSP dtc:    `qcom,gpu-freq = <0x38074300>;`  (940 MHz)
  A text edit of the string form silently corrupts the value.
- It is noisier and less faithful to the phandle / `__symbols__` / `/memreserve/`
  layout that overlay-capable Qualcomm trees carry.

The AOSP dtc is `DTC 1.4.4-Android-build`, built from
`github.com/xzr467706992/dtc-aosp` (the AOSP `external/dtc`). A prebuilt x86_64
binary is committed at `prebuilt/dtc-aosp-x86_64`; `scripts/setup.sh` rebuilds
it if missing. This is the same dtc lineage KonaBess ships to run on device.

## The appended-FDT container

Qualcomm boot/vendor_boot images store one FDT per SoC variant, simply
concatenated. There is no QCDT header table on these parts; the bootloader
selects the matching tree at runtime by `qcom,msm-id` / `qcom,board-id`, and by
index via `ro.boot.dtb_idx`.

- Split: scan for the FDT magic `d0 0d fe ed`, read each FDT's own `totalsize`
  (big-endian u32 at magic+4) and advance by it. `tools/dtb/split_dtb.py`.
- Join: plain in-order concatenation, each FDT self-describes its size. Order
  MUST match the split order. `tools/dtb/join_dtb.py`.

## Round-trip fidelity (measured)

True byte-for-byte identity with the vendor blob is not achievable through any
dtc. The vendor toolchain merges the string table (short property names stored
as suffixes of longer ones); dtc lays the string table out differently, which
shifts string offsets and therefore the struct-block bytes. On every one of the
15 trees in this package the recompiled DTB is exactly 22 bytes larger (a few
duplicate short strings such as `proxy_rx`, `loopback`, `proxy_tx` that the
vendor had suffix-merged).

The guarantee that matters for booting is semantic identity, and it holds:

```
tools/dtb/verify_roundtrip.sh stock/dtb/vendor_boot.dtb-section
```

For all 15 trees this reports `SEMANTIC-MATCH` (decompiling the stock DTB and
decompiling the recompiled DTB yield identical DTS) and `idempotent` (a second
recompile is byte-stable). In other words the recompiled tree describes exactly
the same device; the device parses it identically. Chasing byte-identity would
require reimplementing the vendor's string suffix-merge and buys nothing
functional.

## Editing: the format the device expects

Because the struct block round-trips faithfully, an edit made in the DTS
produces a device-correct DTB. A surgical GPU overclock edit changes only the
intended lines:

```
dtc=prebuilt/dtc-aosp-x86_64
$dtc -q -I dtb -O dts stock/dtb/06.dtb -o work.dts
# edit qcom,gpu-freq etc. in work.dts
$dtc -q -I dts -O dtb work.dts -o modified/dtb/06.parrot.edited.dtb
# confirm the diff is only your change:
diff <($dtc -q -I dtb -O dts stock/dtb/06.dtb) <($dtc -q -I dtb -O dts modified/dtb/06.parrot.edited.dtb)
```

Rules for adding or removing nodes so the tree stays valid:

- Keep `#address-cells` / `#size-cells` consistent; two-cell values render as
  `<0x0 0xVALUE>`. `qcom,gpu-freq` is a single cell.
- If you reference another node by `&label` or phandle, that label must resolve.
  The AOSP dtc regenerates phandles correctly on recompile.
- When adding a GPU pwrlevel, renumber the `reg` indices contiguously and fix
  `qcom,initial-pwrlevel` / `qcom,ca-target-pwrlevel`. See
  `docs/04-overclocking-research.md`.
- After any edit, run the recompile+decompile diff above and re-split/rejoin,
  then repack the image.

## Repack path (via the patched boot image editor)

`patches/abie-use-aosp-dtc.patch` makes cfig's Android_boot_image_editor honour
an `AOSP_DTC` environment variable so its unpack/repack uses our AOSP dtc instead
of the distro dtc. Apply it after `scripts/setup.sh` clones abie:

```
cd external/abie && git apply ../../patches/abie-use-aosp-dtc.patch
export AOSP_DTC=$(pwd)/../../prebuilt/dtc-aosp-x86_64
./gradlew unpack   # dtb decompiles with AOSP dtc (gpu-freq shows as <0x..>)
# edit build/unzip_boot/dtb.N.dts
./gradlew pack     # repacks vendor_boot.img
```

Alternatively edit the split DTBs directly with the tools above and rebuild the
dtb section, which avoids the Gradle toolchain entirely.

This path is validated on this package. `scripts/repack_vendor_boot.sh`
automates it: it unpacks with the patched abie (AOSP dtc), edits the chosen SoC
family's trees, and repacks. The repacked 100MB vendor_boot.img re-extracts to
15 valid FDTs with the edit present. Example:

```
scripts/repack_vendor_boot.sh /mnt/c/55g1/.../vendor_boot.img parrot 1000 \
    modified/firmware/vendor_boot.parrot.gpu1000.img
```

## Overclock edit helpers

- `scripts/gpu_overclock.sh <dtb> <MHz> <out.dtb>` rewrites the existing top
  level's frequency (all speed-bins).
- `tools/dtb/add_gpu_level.py <in.dts> <MHz> <out.dts>` inserts a NEW top level
  above the stock top in every speed-bin and bumps `qcom,initial-pwrlevel` so
  the default operating point is unchanged. Safer: the stock levels stay exactly
  as validated and the device only reaches the new level under full load. Both
  are exercised against the Parrot tree and recompile cleanly.

## AVB / vbmeta note

The dtb lives inside vendor_boot, which is covered by the top-level vbmeta.
Repacking vendor_boot changes its hash. Correction to an earlier assumption: the
standalone `vbmeta.img` on this package IS signed (SHA256_RSA4096, flags=0,
enforced) and hashes boot/vendor_boot/etc. Only vendor_boot's own embedded AVB
footer is unsigned. So a repacked vendor_boot will be rejected by the stock
vbmeta.

Since the OEM RSA4096 private key is not available, the route (on an unlocked
bootloader) is a verification-disabled vbmeta: `scripts/make_disabled_vbmeta.sh`
produces one with the VERIFICATION_DISABLED flag (0x2), after which the modified
vendor_boot boots. See `docs/05`. This is separate from the XBL/ABL secure-boot
chain in `docs/01`.

The vbmeta also confirms the target: build fingerprint
`qti/parrot/parrot:12/.../userdebug/test-keys` (Parrot / SM6450, Android 12,
userdebug, test-keys).
