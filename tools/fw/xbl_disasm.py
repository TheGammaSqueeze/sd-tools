#!/usr/bin/env python3
# Segment-accurate AArch64 scanner for EPSS base-address materialization + LUT stores.
import struct, sys
from capstone import *
from capstone.arm64 import *

def load_segs(fn):
    d=open(fn,'rb').read()
    is64=d[4]==2
    if is64:
        phoff=struct.unpack_from('<Q',d,32)[0]
        phentsize,phnum=struct.unpack_from('<HH',d,54)
        segs=[]
        for i in range(phnum):
            o=phoff+i*phentsize
            typ,flags=struct.unpack_from('<II',d,o)
            off,va=struct.unpack_from('<QQ',d,o+8)
            fsz=struct.unpack_from('<Q',d,o+32)[0]
            if typ==1 and fsz: segs.append((va,off,fsz))
        return d,segs
    else:
        phoff=struct.unpack_from('<I',d,28)[0]
        phentsize,phnum=struct.unpack_from('<HH',d,42)
        segs=[]
        for i in range(phnum):
            o=phoff+i*phentsize
            typ,off,va,pa,fsz=struct.unpack_from('<IIIII',d,o)
            if typ==1 and fsz: segs.append((va,off,fsz))
        return d,segs

# For uefi FV we just treat whole ph1 as flat and scan.
TARGETS={0x17d90000:'L3',0x17d91000:'dom0',0x17d92000:'dom1',0x17aa0000:'apss'}

def scan_a64(code, base):
    # Tracks adrp+add and movz/movk materialization of any addr in the EPSS/APSS window,
    # and flags str/stp stores into base+0x100..0x2FC (the FREQ_LUT programming window).
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM); md.detail=True
    adrp={}        # reg -> adrp page base
    regval={}      # reg -> fully materialized value (adrp+add or movz/movk)
    materialized=[]
    for insn in md.disasm(code, base):
        m=insn.mnemonic; ops=insn.operands
        if m=='adrp':
            adrp[ops[0].reg]=ops[1].imm
        elif m=='add' and len(ops)==3 and ops[2].type==ARM64_OP_IMM:
            rn=ops[1].reg
            if rn in adrp:
                val=adrp[rn]+ops[2].imm
                regval[ops[0].reg]=val
                if 0x17aa0000<=val<0x17e00000:
                    materialized.append((insn.address,insn.reg_name(ops[0].reg),val))
        elif m=='movz' and len(ops)>=2 and ops[1].type==ARM64_OP_IMM:
            sh=getattr(ops[1],'shift',None)
            shv=sh.value if sh and sh.value else 0
            regval[ops[0].reg]=ops[1].imm<<shv
        elif m=='movk' and len(ops)>=2 and ops[1].type==ARM64_OP_IMM:
            sh=getattr(ops[1],'shift',None)
            shv=sh.value if sh and sh.value else 0
            cur=regval.get(ops[0].reg,0)
            cur=(cur & ~(0xffff<<shv)) | (ops[1].imm<<shv)
            regval[ops[0].reg]=cur
            if 0x17aa0000<=cur<0x17e00000:
                materialized.append((insn.address,insn.reg_name(ops[0].reg),cur))
        # flag stores into a base register that currently holds an EPSS-window address
        if m in ('str','stur','stp'):
            for op in ops:
                if op.type==ARM64_OP_MEM and op.mem.base in regval:
                    b=regval[op.mem.base]
                    if (b & ~0xfff) in TARGETS and 0x100<=(op.mem.disp)<=0x2fc:
                        print(f"  LUT STORE {insn.address:#x}: {insn.mnemonic} {insn.op_str}  "
                              f"(base {b:#x} {TARGETS.get(b & ~0xfff,'')} + {op.mem.disp:#x})")
    return materialized

if __name__=='__main__':
    fn=sys.argv[1]
    d,segs=load_segs(fn)
    print(f"{fn}: segs={[(hex(v),hex(o),hex(s)) for v,o,s in segs]}")
    for va,off,sz in segs:
        code=d[off:off+sz]
        mats=scan_a64(code,va)
        for a,r,v in mats:
            tag=TARGETS.get(v & ~0xfff,'')
            print(f"  {a:#x}: {r} = {v:#x} {'<== '+TARGETS.get(v,'') if v in TARGETS else ('~'+tag if tag else '')}")
