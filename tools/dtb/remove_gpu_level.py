#!/usr/bin/env python3
"""
remove_gpu_level.py - Remove a GPU pwrlevel from a Qualcomm device tree.

The counterpart to add_gpu_level.py. Removing a level is a valid device-tree edit
as long as the block stays contiguous: reg indices renumbered 0..N-1, the node
names @0..@N-1 in order, and qcom,initial-pwrlevel / qcom,ca-target-pwrlevel kept
in range and still pointing at the same physical operating point where possible.

Use cases: drop the lowest (slowest) level to keep the GPU clocked higher at idle,
or revert an added top level. Default removes the LOWEST level (highest reg index,
the slowest freq). --index N removes pwrlevel@N in each block instead.

For each qcom,gpu-pwrlevels-N block it:
  - deletes the target pwrlevel node,
  - renumbers the remaining reg = <..> and pwrlevel@.. to 0..N-1 contiguously,
  - clamps qcom,initial-pwrlevel / qcom,ca-target-pwrlevel to the new max index,
    and decrements them if the removed level sat at or below them so they keep
    pointing at the same real level.

Usage:
    remove_gpu_level.py <in.dts> <out.dts> [--index N | --lowest | --top]

Work on the AOSP-dtc decompiled DTS (see docs/02). Recompile with the AOSP dtc.
"""
import sys, re


def find_blocks(text, marker="qcom,gpu-pwrlevels-"):
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


def level_nodes(block):
    """Return list of (start, end, index) for each pwrlevel@N node in the block."""
    nodes = []
    for m in re.finditer(r"qcom,gpu-pwrlevel@(\d+)\s*\{", block):
        idx = int(m.group(1))
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
        end = j + 1
        # include a trailing ';' and following whitespace/newline
        while end < len(block) and block[end] in ";\n\t ":
            end += 1
        nodes.append((m.start(), end, idx))
    return nodes


def process_block(block, which):
    nodes = level_nodes(block)
    if len(nodes) <= 1:
        return block, False
    maxidx = max(n[2] for n in nodes)
    target = {"lowest": maxidx, "top": 0}.get(which, which)
    tnode = next((n for n in nodes if n[2] == target), None)
    if tnode is None:
        return block, False
    # delete the target node text
    block = block[:tnode[0]] + block[tnode[1]:]

    # renumber remaining reg and @N to 0..N-1 in source order. Use a two-pass
    # placeholder so a rename like @8->@7 cannot collide with an existing @7 that
    # is itself about to become @6.
    remaining = [n[2] for n in nodes if n[2] != target]
    remap = {old: new for new, old in enumerate(sorted(remaining))}
    # pass 1: @old -> @@new@@ placeholder
    for old in remap:
        block = re.sub(rf"qcom,gpu-pwrlevel@{old}(\s*\{{)",
                       f"qcom,gpu-pwrlevel@@{remap[old]}@@\\1", block)
    block = re.sub(r"qcom,gpu-pwrlevel@@(\d+)@@", r"qcom,gpu-pwrlevel@\1", block)
    # reg is a single independent per-match map (no collision risk)
    block = re.sub(r"reg = <(0x[0-9a-fA-F]+|\d+)>",
                   lambda m: (f"reg = <{hex(remap[int(m.group(1), 0)])}>"
                             if int(m.group(1), 0) in remap else m.group(0)),
                   block)

    # fix initial-pwrlevel / ca-target-pwrlevel
    def fix_prop(s, prop):
        def repl(mm):
            v = int(mm.group(1), 0)
            if v == target:
                v = min(v, len(remaining) - 1)      # removed the default; clamp
            elif v > target:
                v -= 1                               # shift down past the hole
            v = max(0, min(v, len(remaining) - 1))
            return f"{prop} = <{hex(v)}>"
        return re.sub(prop + r" = <(0x[0-9a-fA-F]+|\d+)>", repl, s)

    block = fix_prop(block, "qcom,initial-pwrlevel")
    block = fix_prop(block, "qcom,ca-target-pwrlevel")
    return block, True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    which = "lowest"
    for a in sys.argv[1:]:
        if a == "--top":
            which = "top"
        elif a == "--lowest":
            which = "lowest"
        elif a.startswith("--index="):
            which = int(a.split("=", 1)[1])
        elif a == "--index" and args:
            pass
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    text = open(args[0]).read()
    spans = find_blocks(text)
    if not spans:
        print("no qcom,gpu-pwrlevels-N blocks found")
        sys.exit(2)
    out = text
    count = 0
    for (s, e) in sorted(spans, reverse=True):
        nb, ok = process_block(out[s:e], which)
        if ok:
            out = out[:s] + nb + out[e:]
            count += 1
    open(args[1], "w").write(out)
    print(f"removed the {which} level from {count} speed-bin(s) -> {args[1]}")


if __name__ == "__main__":
    main()
