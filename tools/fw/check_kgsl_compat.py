#!/usr/bin/env python3
"""
check_kgsl_compat.py - Will this Mesa/Turnip build run on this device's kernel?

On Android the gating factor for whether a given Turnip runs is the KGSL kernel
ABI: Turnip's KGSL backend (src/freedreno/vulkan/tu_knl_kgsl.cc) calls a fixed
set of IOCTL_KGSL_* and works only if the kernel's msm_kgsl.ko implements them.
This tool extracts the ioctls the kernel module supports and diffs them against
the set a Mesa checkout requires (or a built-in reference set), reporting whether
that Mesa version can run on that kernel.

Kernel side: the module registers handlers named kgsl_ioctl_<name> and
adreno_ioctl_<name>; we scan those strings.

Mesa side: pass --mesa <path-to-tu_knl_kgsl.cc> to read the exact required set
from source, or omit it to use REQUIRED_MAIN (the set Mesa main uses, captured
here). Perfcounter is profiling-only and reported separately.

Usage:
    check_kgsl_compat.py <msm_kgsl.ko> [--mesa <tu_knl_kgsl.cc>]
"""
import sys, re, subprocess

# The IOCTL_KGSL_* set Mesa main's tu_knl_kgsl.cc calls (captured 2026, verify
# with --mesa against your checkout). Names are the part after IOCTL_KGSL_.
REQUIRED_MAIN = {
    "device_getproperty", "device_waittimestamp_ctxtid", "drawctxt_create",
    "drawctxt_destroy", "gpumem_alloc_id", "gpumem_bind_ranges", "gpumem_free_id",
    "gpumem_get_info", "gpuobj_alloc", "gpuobj_free", "gpuobj_import",
    "gpuobj_info", "gpu_aux_command", "gpu_command", "timestamp_event",
}
# profiling-only; absence just disables perf-counter queries, not rendering
OPTIONAL = {"perfcounter_read"}


def kernel_ioctls(path):
    # Accept either a msm_kgsl.ko (scanned with strings) or a pre-extracted
    # ioctl-list .txt (one name per line, '#' comments), e.g. the committed
    # gpu/device-kgsl/msm_kgsl.ioctls.txt.
    if path.endswith(".txt"):
        text = open(path, "r", errors="replace").read()
    else:
        text = subprocess.run(["strings", path], capture_output=True).stdout.decode("latin1")
    have = set()
    for m in re.finditer(r"(?:kgsl|adreno)_ioctl_([a-z0-9_]+)", text):
        name = re.sub(r"_compat$", "", m.group(1))  # _compat = the 32-bit thunk
        have.add(name)
    return have


def mesa_required(src_path):
    txt = open(src_path).read()
    return {m.lower() for m in re.findall(r"IOCTL_KGSL_([A-Z0-9_]+)", txt)}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ko = sys.argv[1]
    req = REQUIRED_MAIN
    opt = OPTIONAL
    if "--mesa" in sys.argv:
        src = sys.argv[sys.argv.index("--mesa") + 1]
        allreq = mesa_required(src)
        opt = {x for x in allreq if "perfcounter" in x}
        req = allreq - opt

    have = kernel_ioctls(ko)
    missing = sorted(r for r in req if r not in have)
    missing_opt = sorted(o for o in opt if o not in have)

    print(f"# kernel module: {ko}")
    print(f"# kernel implements {len(have)} kgsl/adreno ioctls")
    print(f"# Turnip requires {len(req)} (+{len(opt)} optional)")
    modern = ["gpumem_bind_ranges", "gpu_aux_command", "gpuobj_import"]
    print("modern-feature ioctls present:",
          ", ".join(f"{m}={'yes' if m in have else 'NO'}" for m in modern))
    if missing:
        print("\nMISSING required ioctls (this Mesa will NOT run):")
        for m in missing:
            print("  -", m)
    else:
        print("\nRESULT: all required ioctls present. This Turnip build will run on this kernel.")
    if missing_opt:
        print("optional-not-present (profiling only, safe):", ", ".join(missing_opt))
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
