#!/usr/bin/env python3
"""
add_gpu_level.py - Insert a new top GPU pwrlevel into a Qualcomm device tree.

Unlike scripts/gpu_overclock.sh (which only rewrites the frequency of the
existing top level), this ADDS a new fastest level above the stock top in every
speed-bin, which is the safer overclock: the stock top level stays exactly as
validated, the device only reaches the new level under full load, and you can
back it out by removing one node.

For each qcom,gpu-pwrlevels-N block it:
  - clones the current pwrlevel@0 (the stock top),
  - sets the clone's qcom,gpu-freq to the requested MHz,
  - inserts it as the new pwrlevel@0,
  - renumbers every reg = <N> and every pwrlevel@N in the block by +1,
  - bumps qcom,initial-pwrlevel and qcom,ca-target-pwrlevel by 1 so the default
    operating point is unchanged (the device does not boot at the new level).

The clone keeps the stock qcom,level (voltage corner, normally TURBO 0x1a0),
qcom,acd-level and the bus votes, so the new level runs at the top validated
voltage. Raising voltage beyond TURBO is not possible from the DTB.

Usage:
    add_gpu_level.py <in.dts> <MHz> <out.dts>

Work on the AOSP-dtc decompiled DTS (see docs/02). Recompile with the AOSP dtc.
"""
import sys, re


def find_blocks(text, marker="qcom,gpu-pwrlevels-"):
    """Yield (start, end) spans of each pwrlevels-N block body (brace-matched)."""
    spans = []
    for m in re.finditer(re.escape(marker) + r"\d+\s*\{", text):
        i = text.index("{", m.start())
        depth = 0
        j = i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        spans.append((m.start(), j + 1))
    return spans


def process_block(block, new_hex):
    # Grab the stock pwrlevel@0 sub-node (brace-matched).
    m = re.search(r"qcom,gpu-pwrlevel@0\s*\{", block)
    if not m:
        return block, False
    i = block.index("{", m.start())
    depth = 0
    j = i
    while j < len(block):
        if block[j] == "{":
            depth += 1
        elif block[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    node = block[m.start():j + 1]

    # Renumber existing levels: reg = <N> -> <N+1>, and @N -> @N+1 (high to low).
    def bump_regs(s):
        regs = sorted({int(x, 0) for x in re.findall(r"reg = <(0x[0-9a-fA-F]+|\d+)>", s)},
                      reverse=True)
        for r in regs:
            s = s.replace(f"reg = <{hex(r)}>", f"reg = <{hex(r + 1)}>")
            s = s.replace(f"reg = <{r}>", f"reg = <{r + 1}>")
        return s

    def bump_names(s):
        idxs = sorted({int(x) for x in re.findall(r"qcom,gpu-pwrlevel@(\d+)", s)},
                      reverse=True)
        for k in idxs:
            s = s.replace(f"qcom,gpu-pwrlevel@{k} ", f"qcom,gpu-pwrlevel@{k + 1} ")
            s = s.replace(f"qcom,gpu-pwrlevel@{k}\t", f"qcom,gpu-pwrlevel@{k + 1}\t")
        return s

    renum = bump_names(bump_regs(block))

    # Build the new top node from a clone of the stock top, reg=0, new freq.
    new_node = re.sub(r"qcom,gpu-freq = <0x[0-9a-fA-F]+>",
                      f"qcom,gpu-freq = <{new_hex}>", node)
    new_node = re.sub(r"reg = <(0x[0-9a-fA-F]+|\d+)>", "reg = <0x0>", new_node, count=1)

    # Insert the new node right before the (now @1) first level.
    anchor = re.search(r"\n(\s*)qcom,gpu-pwrlevel@1\s*\{", renum)
    indent = anchor.group(1)
    insert_at = anchor.start() + 1
    renum = renum[:insert_at] + indent + new_node.strip() + ";\n\n" + renum[insert_at:]

    # Bump initial-pwrlevel / ca-target-pwrlevel by 1 (keep the same real default).
    def bump_prop(s, prop):
        def repl(mm):
            return f"{prop} = <{hex(int(mm.group(1), 0) + 1)}>"
        return re.sub(prop + r" = <(0x[0-9a-fA-F]+|\d+)>", repl, s)

    renum = bump_prop(renum, "qcom,initial-pwrlevel")
    renum = bump_prop(renum, "qcom,ca-target-pwrlevel")
    return renum, True


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    text = open(sys.argv[1]).read()
    mhz = int(sys.argv[2])
    new_hex = hex(mhz * 1000000)
    spans = find_blocks(text)
    if not spans:
        print("no qcom,gpu-pwrlevels-N blocks found (single-bin part? use gpu_overclock.sh)")
        sys.exit(2)
    # Rebuild the text back-to-front so earlier offsets stay valid.
    out = text
    count = 0
    for (s, e) in sorted(spans, reverse=True):
        new_block, ok = process_block(out[s:e], new_hex)
        if ok:
            out = out[:s] + new_block + out[e:]
            count += 1
    open(sys.argv[3], "w").write(out)
    print(f"added a {mhz} MHz top level ({new_hex}) to {count} speed-bin(s) -> {sys.argv[3]}")


if __name__ == "__main__":
    main()
