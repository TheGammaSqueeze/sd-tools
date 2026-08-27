#!/usr/bin/env python3
"""
inspect_mbn.py - Inspect a Qualcomm signed ELF image (XBL, ABL, TZ, AOP, ...).

Prints the ELF program headers, locates the Qualcomm hash-table segment (the
program header carrying the per-segment SHA hashes + signature + cert chain),
and extracts every embedded X.509 certificate so you can read the signing
identity (production OEM keys vs Qualcomm SecTools test keys) and the
signature algorithm.

The hash-table segment on these parts is the program header with p_flags high
bits set (0x2000000 / 0x1000000 family) rather than a normal RWE LOAD.

Usage:
    inspect_mbn.py <image.elf> [--dump-certs OUTDIR]

Requires: openssl on PATH for the human-readable cert summary (optional).
"""
import sys, struct, subprocess, os, shutil

DER_SEQ = b"\x30\x82"


def parse_elf(d):
    is64 = d[4] == 2
    if is64:
        e_phoff = struct.unpack("<Q", d[32:40])[0]
        e_phentsize = struct.unpack("<H", d[54:56])[0]
        e_phnum = struct.unpack("<H", d[56:58])[0]
    else:
        e_phoff = struct.unpack("<I", d[28:32])[0]
        e_phentsize = struct.unpack("<H", d[42:44])[0]
        e_phnum = struct.unpack("<H", d[44:46])[0]
    phs = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        if is64:
            p_type = struct.unpack("<I", d[o:o + 4])[0]
            p_flags = struct.unpack("<I", d[o + 4:o + 8])[0]
            p_offset = struct.unpack("<Q", d[o + 8:o + 16])[0]
            p_filesz = struct.unpack("<Q", d[o + 32:o + 40])[0]
        else:
            p_type = struct.unpack("<I", d[o:o + 4])[0]
            p_offset = struct.unpack("<I", d[o + 4:o + 8])[0]
            p_filesz = struct.unpack("<I", d[o + 16:o + 20])[0]
            p_flags = struct.unpack("<I", d[o + 24:o + 28])[0]
        phs.append(dict(idx=i, type=p_type, off=p_offset, filesz=p_filesz, flags=p_flags))
    return is64, phs


def find_certs(d):
    certs = []
    i = 0
    while True:
        i = d.find(DER_SEQ, i)
        if i < 0:
            break
        ln = (d[i + 2] << 8) | d[i + 3]
        if 200 < ln < 5000 and i + 4 + ln <= len(d):
            certs.append((i, d[i:i + 4 + ln]))
            i += 4 + ln
        else:
            i += 2
    return certs


def openssl_summary(der):
    if not shutil.which("openssl"):
        return "(openssl not found)"
    try:
        out = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-noout", "-subject", "-issuer"],
            input=der, capture_output=True).stdout.decode("utf-8", "replace").strip()
        alg = subprocess.run(
            ["openssl", "x509", "-inform", "DER", "-noout", "-text"],
            input=der, capture_output=True).stdout.decode("utf-8", "replace")
        for line in alg.splitlines():
            if "Signature Algorithm" in line:
                out += "\n  " + line.strip()
                break
        return out
    except Exception as e:
        return f"(openssl error: {e})"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    fn = sys.argv[1]
    dumpdir = None
    if "--dump-certs" in sys.argv:
        dumpdir = sys.argv[sys.argv.index("--dump-certs") + 1]
        os.makedirs(dumpdir, exist_ok=True)
    d = open(fn, "rb").read()
    print(f"# {fn}  ({len(d)} bytes)")
    is64, phs = parse_elf(d)
    print(f"ELF{'64' if is64 else '32'}  {len(phs)} program headers")
    for p in phs:
        tag = ""
        if p["flags"] & 0xFF000000:
            tag = "  <- Qualcomm hash/sign segment" if p["type"] == 0 or p["flags"] & 0x2000000 else "  <- flagged"
        print(f"  ph[{p['idx']}] type={p['type']:#x} off={p['off']:#010x} "
              f"filesz={p['filesz']:#x} flags={p['flags']:#010x}{tag}")
    certs = find_certs(d)
    print(f"\n{len(certs)} embedded X.509 certificate(s):")
    roles = ["leaf/attestation", "attestation CA", "root"]
    # The signing chain is usually the last 3 certs (leaf, CA, root).
    chain = certs[-3:] if len(certs) >= 3 else certs
    for n, (off, der) in enumerate(chain):
        role = roles[n] if n < len(roles) else f"cert{n}"
        print(f"\n[{role}] at {off:#x}:")
        print("  " + openssl_summary(der).replace("\n", "\n  "))
        if dumpdir:
            path = os.path.join(dumpdir, f"{os.path.basename(fn)}.{role.split('/')[0]}.der")
            open(path, "wb").write(der)
    if dumpdir:
        print(f"\ncerts dumped to {dumpdir}")


if __name__ == "__main__":
    main()
