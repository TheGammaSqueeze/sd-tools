#!/usr/bin/env python3
# KGSL (msm adreno) snapshot parser -> extract register (offset,value) pairs.
# REGS section body = [u32 count][count*(u32 offset, u32 value)].
import sys, struct
data = open(sys.argv[1],'rb').read()
SECT=0xABCD
IDS={0x0101:'OS',0x0201:'REGS',0x0301:'RB',0x0401:'IB',0x0501:'INDEXED_REGS',
     0x0d01:'SHADER',0x0e01:'MVC',0x0e02:'MVC_V2',0x0b02:'MEMLIST_V2',
     0x1001:'GMU',0x0402:'IB_V2',0x0302:'RB_V2',0x1501:'GMU_MEM',0x1a01:'SIDEBAND2'}
off=12
regs={}
counts={}
while off<len(data)-8:
    magic,sid=struct.unpack_from('<HH',data,off)
    if magic!=SECT: off+=4; continue
    size=struct.unpack_from('<I',data,off+4)[0]
    name=IDS.get(sid,f'0x{sid:04x}'); counts[name]=counts.get(name,0)+1
    if size<8 or off+size>len(data): break
    if sid==0x0201:  # REGS
        body=data[off+8:off+size]
        if len(body)>=4:
            cnt=struct.unpack_from('<I',body,0)[0]
            for i in range(cnt):
                p=4+i*8
                if p+8>len(body): break
                o,v=struct.unpack_from('<II',body,p)
                regs[o]=v
    off+=size
print("sections:",counts)
print(f"total regs: {len(regs)}")
# a6xx graphics config regs of interest (dword offsets)
NAMES={0x8804:'RB_BIN_CONTROL',0x88d1:'RB_CCU_CNTL',0x8c00:'RB_CCU_CNTL2',
 0x80a1:'GRAS_BIN_CONTROL',0x8000:'GRAS_CL_CNTL',0x8600:'GRAS_LRZ_CNTL',
 0x8809:'RB_CCU_CACHE_CNTL',0x9210:'VPC_SO_CNTL',0x8110:'RB_RENDER_CNTL',
 0x8e07:'RB_UNKNOWN_8E07',0x0e00:'RBBM',0x8101:'RB_UNKNOWN'}
if len(sys.argv)>2:
    # print regs in a range
    lo,hi=int(sys.argv[2],0),int(sys.argv[3],0)
    for o in sorted(regs):
        if lo<=o<=hi:
            n=NAMES.get(o,'')
            print(f"  0x{o:05x} = 0x{regs[o]:08x}  {n}")
