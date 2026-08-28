#!/usr/bin/env python3
"""Parse campaign results (bench/results/<label>/) into a markdown table for
docs/14-benchmarks.md. Reports per-component numbers and, for every non-baseline
label, the delta against the 'baseline' run. Also emits the combined-stress
sustained clocks and peak temperature for stability tracking."""
import os, re, sys

def num(pat, text):
    m = re.search(pat, text)
    return float(m.group(1)) if m else None

def parse_label(d):
    r = {}
    pc = os.path.join(d, "percomponent.txt")
    if os.path.exists(pc):
        t = open(pc).read()
        for line in t.splitlines():
            if line.startswith("CPU_BIG"):
                r["cpu_big_mops"] = num(r"mops=([\d.]+)", line)
            elif line.startswith("CPU_LITTLE"):
                r["cpu_little_mops"] = num(r"mops=([\d.]+)", line)
            elif line.startswith("MEM"):
                r["mem_read"] = num(r"read_GBps=([\d.]+)", line)
                r["mem_copy"] = num(r"copy_GBps=([\d.]+)", line)
                r["mem_lat"] = num(r"latency_ns=([\d.]+)", line)
        if "gflops" in t:
            r["gpu_gflops"] = num(r"gflops=([\d.]+)", t)
        r["gpu_maxhz"] = num(r"gpu_maxhz=(\d+)", t)
        r["cpu_big_maxkhz"] = num(r"cpu_big_maxkhz=(\d+)", t)
        r["temp_after"] = num(r"temp_after_mC=(\d+)", t)
    cb = os.path.join(d, "combined.txt")
    if os.path.exists(cb):
        t = open(cb).read()
        r["comb_gpu"] = num(r"gpu=(\d+)", t)
        r["comb_cpu_big"] = num(r"cpu_big=(\d+)", t)
        r["comb_peak_temp"] = num(r"temp=(\d+)", t)
        r["comb_fail"] = "yes" if re.search(r"_FAIL", t) else "no"
    return r

def fmt(v, scale=1.0, nd=1):
    return "-" if v is None else f"{v/scale:.{nd}f}"

def delta(cur, base):
    if cur is None or base is None or base == 0:
        return ""
    return f" ({(cur-base)/base*100:+.1f}%)"

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "bench/results"
    labels = sorted(x for x in os.listdir(root) if os.path.isdir(os.path.join(root, x)))
    data = {l: parse_label(os.path.join(root, l)) for l in labels}
    base = data.get("baseline", {})

    print("### Per-component (mode B): baseline vs overclock\n")
    print("| Run | GPU MHz | GPU GFLOPS | CPU big MHz | CPU big mops | CPU little mops | MEM copy GB/s | MEM lat ns | peak temp C |")
    print("|-----|---------|-----------|-------------|--------------|-----------------|---------------|-----------|-------------|")
    for l in labels:
        r = data[l]
        row = [
            l,
            fmt(r.get("gpu_maxhz"), 1e6, 0),
            fmt(r.get("gpu_gflops")) + delta(r.get("gpu_gflops"), base.get("gpu_gflops")),
            fmt(r.get("cpu_big_maxkhz"), 1e3, 0),
            fmt(r.get("cpu_big_mops")) + delta(r.get("cpu_big_mops"), base.get("cpu_big_mops")),
            fmt(r.get("cpu_little_mops")) + delta(r.get("cpu_little_mops"), base.get("cpu_little_mops")),
            fmt(r.get("mem_copy")) + delta(r.get("mem_copy"), base.get("mem_copy")),
            fmt(r.get("mem_lat")),
            fmt(r.get("temp_after"), 1e3, 1),
        ]
        print("| " + " | ".join(row) + " |")

    print("\n### Combined all-max stress (mode A): sustained clocks + stability\n")
    print("| Run | GPU MHz sustained | CPU big MHz sustained | peak temp C | all workers survived |")
    print("|-----|-------------------|-----------------------|-------------|----------------------|")
    for l in labels:
        r = data[l]
        row = [
            l,
            fmt(r.get("comb_gpu"), 1e6, 0),
            fmt(r.get("comb_cpu_big"), 1e3, 0),
            fmt(r.get("comb_peak_temp"), 1e3, 1),
            r.get("comb_fail", "-") == "no" and "yes" or ("no" if r.get("comb_fail") == "yes" else "-"),
        ]
        print("| " + " | ".join(row) + " |")

if __name__ == "__main__":
    main()
