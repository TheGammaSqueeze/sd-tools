#!/usr/bin/env python3
"""
cpucp_disasm.py - Load each PT_LOAD of a RISC-V ELF32 at its real VADDR and
disassemble with capstone, resolving lui/addi/auipc address materialization.

Usage:
  cpucp_disasm.py <elf> materialize <hexconst>   # find code building an address
  cpucp_disasm.py <elf> dis <vaddr> <count>       # disassemble N insns from vaddr
  cpucp_disasm.py <elf> stores <vaddr> <count>    # dump, flag store insns
  cpucp_disasm.py <elf> segs                       # list loadable segments
"""
import sys, struct
from capstone import Cs, CS_ARCH_RISCV, CS_MODE_RISCV32

def load_segs(path):
    d = open(path, "rb").read()
    phoff = struct.unpack_from("<I", d, 0x1c)[0]
    phentsize = struct.unpack_from("<H", d, 0x2a)[0]
    phnum = struct.unpack_from("<H", d, 0x2c)[0]
    segs = []
    for i in range(phnum):
        b = phoff + i*phentsize
        p_type, p_off, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
            struct.unpack_from("<IIIIIIII", d, b)
        if p_type == 1 and p_filesz > 0:
            segs.append(dict(off=p_off, vaddr=p_paddr, filesz=p_filesz,
                             memsz=p_memsz, flags=p_flags,
                             data=d[p_off:p_off+p_filesz]))
    return d, segs

def md():
    m = Cs(CS_ARCH_RISCV, CS_MODE_RISCV32)
    m.detail = True
    return m

def exec_segs(segs):
    return [s for s in segs if s["flags"] & 1]

def dis_seg(seg, m):
    # returns list of (addr, mnemonic, op_str, size, bytes)
    out = []
    for ins in m.disasm(seg["data"], seg["vaddr"]):
        out.append((ins.address, ins.mnemonic, ins.op_str, ins.size, ins.bytes))
    return out

def find_materialize(segs, target):
    m = md()
    hi = target & 0xfffff000
    lo = target & 0xfff
    # signed adjust: addi sign-extends 12-bit
    lo_signed = lo if lo < 0x800 else lo - 0x1000
    hi_adj = (target - lo_signed) & 0xffffffff
    print(f"target=0x{target:08x} lui_imm(hi)=0x{hi:08x} adj_hi=0x{hi_adj:08x} addi_lo={lo_signed}")
    for seg in exec_segs(segs):
        insns = dis_seg(seg, m)
        # track register upper values from lui/auipc
        regval = {}
        for (addr, mn, ops, sz, bs) in insns:
            parts = [p.strip() for p in ops.split(',')]
            if mn == 'lui' and len(parts) == 2:
                try:
                    rd = parts[0]; imm = int(parts[1], 0)
                    regval[rd] = (imm << 12) & 0xffffffff if imm < 0x100000 else imm & 0xffffffff
                    # capstone often already shifts; handle both
                    v = imm & 0xffffffff
                    regval[rd] = v if v & 0xfff == 0 else (imm<<12)&0xffffffff
                except: pass
            elif mn == 'auipc' and len(parts) == 2:
                try:
                    rd = parts[0]; imm = int(parts[1],0)
                    regval[rd] = (addr + ((imm<<12)&0xffffffff)) & 0xffffffff
                except: pass
            elif mn in ('addi','ori','c.addi') and len(parts) == 3:
                try:
                    rd, rs, imm = parts[0], parts[1], int(parts[2],0)
                    if rs in regval:
                        base = regval[rs]
                        val = (base + imm) & 0xffffffff if mn!='ori' else (base|imm)&0xffffffff
                        regval[rd] = val
                        if val == target:
                            print(f"  HIT @0x{addr:08x}: {mn} {ops}  => 0x{val:08x}  (rs {rs}=0x{base:08x})")
                except: pass
            # also flag raw lui hitting hi
            if mn=='lui':
                try:
                    imm=int(parts[1],0); v=imm&0xffffffff
                    if v==hi_adj or (imm<<12)&0xffffffff==hi_adj:
                        print(f"  lui-hi @0x{addr:08x}: {mn} {ops} (matches hi 0x{hi_adj:08x})")
                except: pass

def dis(segs, vaddr, count, flag_stores=False):
    m = md()
    for seg in exec_segs(segs):
        if seg["vaddr"] <= vaddr < seg["vaddr"]+seg["filesz"]:
            off = vaddr - seg["vaddr"]
            n=0
            for ins in m.disasm(seg["data"][off:], vaddr):
                store = ins.mnemonic in ('sw','sh','sb','c.sw','c.swsp')
                mark = ' <-- STORE' if (flag_stores and store) else ''
                print(f"0x{ins.address:08x}: {ins.mnemonic:10s} {ins.op_str}{mark}")
                n+=1
                if n>=count: return
            return
    print("vaddr not in any exec seg")

def main():
    path=sys.argv[1]; cmd=sys.argv[2]
    d, segs = load_segs(path)
    if cmd=='segs':
        for s in segs:
            print(f"off=0x{s['off']:06x} vaddr=0x{s['vaddr']:08x} filesz=0x{s['filesz']:05x} flags={s['flags']} {'X' if s['flags']&1 else ''}")
    elif cmd=='materialize':
        find_materialize(segs, int(sys.argv[3],0))
    elif cmd=='dis':
        dis(segs, int(sys.argv[3],0), int(sys.argv[4]))
    elif cmd=='stores':
        dis(segs, int(sys.argv[3],0), int(sys.argv[4]), flag_stores=True)

if __name__=='__main__':
    main()
