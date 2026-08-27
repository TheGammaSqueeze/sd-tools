# Secure boot and re-signing XBL / ABL

## The chain of trust

```
PBL (SoC ROM)  -> verifies -> XBL/SBL   against OEM_PK_HASH fuse (or skipped if unfused)
XBL            -> verifies -> ABL (abl.elf), TZ, AOP, devcfg, hyp, cpucp, ...
ABL / UEFI     -> verifies -> boot / vendor_boot / dtbo  via Android Verified Boot (vbmeta)
```

Each of XBL and ABL is an ELF carrying a Qualcomm hash-table segment: a header
with a SHA hash of every loadable ELF segment, followed by the signature over
that header, followed by the DER certificate chain (leaf -> attestation CA ->
root). Modify any loadable segment and its stored hash no longer matches, so the
image must be re-hashed and re-signed. On this SoC the signature is ECDSA
secp384r1 / ecdsa-with-SHA384, which is Qualcomm "Secure Boot 3.0" (MBN header
v6/v7). The sign attributes (SW_ID, HW_ID, OEM_ID, MODEL_ID, DEBUG, anti-rollback
version) live in the hash-segment metadata, not in the cert subject fields.

## What this device is signed with (measured)

`tools/signing/inspect_mbn.py` extracted the cert chain from every firmware
image in the package. All of them (XBL, ABL, TZ, AOP, devcfg, hyp, cpucp, uefi,
keymint, ...) chain to:

```
root: CN = SECTOOLS SECP384R1 CURVE TEST ROOT
      OU = General Use Test Key (for testing only)
alg:  ecdsa-with-SHA384
```

The single exception is `multi_image_qti.mbn`, signed by a genuine QTI
production root ("SRoT MBNv7 Image Signing Root CA 6").

A shipping build that boots test-key-signed XBL/ABL/TZ means the OEM secure-boot
fuse (OEM_PK_HASH) is almost certainly **not blown**. This is the single most
important fact for modification. Verify it before touching XBL.

The device's own three certs are committed under `stock/certs/` for reference.

## Verify the fuse state first (do this before modifying XBL)

Any one of these confirms whether secure boot is enforced:

- On device: `fastboot oem device-info` (look for `secure boot: no`).
- In EDL/QFIL: read the QFPROM `OEM_PK_HASH` region; all-zero (or the test-key
  hash) means open.
- Empirical: the device currently runs test-key-signed XBL. A production-fused
  unit would reject those very images, so booting them is itself strong evidence
  the fuse is open.

## Two re-signing paths

### Path A - device unfused (secure boot off): qtestsign

If the fuse is open, the bootloader does not check the signature value, only the
image format. `tools/signing/qtestsign` produces a correctly-formatted MBN hash
segment with a stub signature. This is the simplest path and is committed in the
repo.

```
python3 tools/signing/qtestsign/qtestsign.py abl  modified/firmware/abl.elf  -o modified/firmware/abl.signed.elf
python3 tools/signing/qtestsign/qtestsign.py xbl  modified/firmware/xbl.elf  -o modified/firmware/xbl.signed.elf
```

qtestsign supports MBN v3/v5/v6/v7 and the image types `abl`, `sbl1` (xbl),
`tz`, `hyp`, `devcfg`, `cpucp`, `aop`, `xbl-config` and more. It does NOT forge a
real signature, so it only works on an unfused device.

`scripts/resign_firmware.sh` wraps it and defaults to MBN v6, which matches this
device's SB3.0 header (SHA384 hash segment). Verified on the ABL: the re-signed
image carries a well-formed v6 hash segment (ph[0] header 0x94 + ph[1] hash and
cert chain), with a stub RSA "NOT SECURE" cert chain. Because `devcfg`, `cpucp`
and `aop` are supported types, this same path re-signs the firmware needed for
the CPU and DDR overclock (see docs/04) on an unfused device, without sectools.
Override the version with `MBN_VERSION=7` if a specific image needs it.

### Path B - device fused to the test root: genuine sectools

If the fuse is blown to the test root the device runs, a real signature under
that exact root is required. Use the genuine QTI `sectools`, vendored in-repo at
`third_party/sectools`. The secp384r1 test key sets are committed under
`third_party/sectools/resources/.../qti_presigned_certs-secp384r1/` and under
`tools/signing/testkeys-secp384r1/`, so the signer is self-contained.

Tool status (validated): the sectools signing pipeline runs end-to-end here
(loads, parses, signs). Running it on the stock ABL reports, from sectools' own
parse, that this device is MBNv7 (SB3.0). The one config the vendored sectools
ships is `config/qcc730` which is MBNv3 / RSA-2048 / SHA256 (SB2.0), the wrong
crypto for this SoC (sectools errors "Downscaling MBNv7 image to MBNv3 image is
not supported"). So the fused-device path needs an MBNv7 / SB3.0 / ECDSA
secp384r1 secimage config for Parrot (SM6450), which the QCC SDK snapshot does
not include. That config must declare `secboot_version` for MBNv7 and the ECDSA
secp384r1 signer, and its `<image sign_id="appsbl">` entry must carry the exact
`msm_part` / `oem_id` / `model_id` / `debug` of this device (read them from the
stock image with `tools/signing/inspect_mbn.py`). Authoring it with any guessed
device value would produce a wrong signature, and it cannot be boot-validated
without a fused unit, so it is deliberately not fabricated here. On an unfused
device (the expected case for this test-keyed build) this whole path is moot:
Path A (qtestsign) is the validated, working route.

Note: the committed presigned chain is the "Generated Test Root CA" variant. The
device's images chain to "SECTOOLS SECP384R1 CURVE TEST ROOT", a different test
root. If the device turns out to be fused (not merely unfused), the exact root
private key whose hash is in the fuse is required; compare
`stock/certs/abl.elf.root.der` against the fuse hash to decide. On an unfused
device this does not matter and Path A is sufficient.

Canonical sectools ABL sign (appsbl group):

```
python3 third_party/sectools/sectools.py secimage \
  -i modified/firmware/abl.elf \
  -g appsbl \
  -c third_party/sectools/config/<chipset>/<chipset>_secimage.xml \
  --cfg_selected_signer qti_presigned \
  --sign -o modified/firmware/out/
```

Swap `-g appsbl` for `xbl`, `tz`, `devcfg`, etc. The `<chipset>_secimage.xml`
must declare `secboot_version=3.0`, `hash_algorithm=sha384` and the secp384r1
signer, and its `<image sign_id="appsbl">` entry supplies SW_ID/HW_ID/OEM_ID/
MODEL_ID/DEBUG. Read those out of the current image with
`tools/signing/inspect_mbn.py` so the re-signed image carries identical
attributes.

## Recoverability

- ABL: a bad ABL is recoverable via EDL (Firehose) or `fastboot flash abl`.
- XBL: a bad XBL drops the device to EDL 9008; recovery needs a signed Firehose
  programmer (`prog_firehose_*` is in the package) plus QFIL. If the fuse is open
  even a broken XBL is EDL-recoverable; if fused, you depend on the stock signed
  loader. Always keep the stock images (they are in `stock/firmware/`).
