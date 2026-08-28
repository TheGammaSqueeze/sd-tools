#!/usr/bin/env python3
# Minimal KGSL (msm adreno) snapshot section parser.
# Walks 0xABCD sections; extracts REGS sections as (offset,value) pairs.
import sys, struct
data = open(sys.argv[1],'rb').read()
SECT_MAGIC = 0xABCD
# section ids (msm kgsl_snapshot.h)
IDS = {0x0101:'OS',0x0201:'REGS',0x0301:'RB',0x0401:'IB',0x0501:'INDEXED_REGS',
       0x0601:'ISTORE',0x0801:'DEBUG',0x0901:'DEBUGBUS',0x0a01:'GPU_OBJECT',
       0x0b01:'MEMLIST',0x0c01:'MEMLIST_V2',0x0d01:'SHADER',0x0e01:'MVC',
       0x0f01:'MVC_V2',0x1001:'GMU',0x1101:'GMU_MEMORY',0x1201:'SIDEBAND'}
# find first section
off = 0
# skip header: find first 0xABCD
while off < len(data)-4:
    magic = struct.unpack_from('<H', data, off)[0]
    if magic == SECT_MAGIC: break
    off += 4
print(f"first section at offset {off}")
regs = {}
counts = {}
while off < len(data)-8:
    magic, sid = struct.unpack_from('<HH', data, off)
    if magic != SECT_MAGIC:
        off += 4; continue
    size = struct.unpack_from('<I', data, off+4)[0]
    name = IDS.get(sid, f'0x{sid:04x}')
    counts[name] = counts.get(name,0)+1
    if size < 8 or off+size > len(data): break
    # REGS section body: header then (offset,value) u32 pairs
    if name == 'REGS':
        body = data[off+8:off+size]
        # msm regs section header: struct {__u32 count;} then count*(u32 offset,u32 value)
        # but format varies; try pairs across the whole body
        npairs = len(body)//8
        for i in range(npairs):
            o,v = struct.unpack_from('<II', body, i*8)
            if 0 < o < 0x40000:  # plausible reg offset
                regs[o]=v
    off += size
print("sections:", counts)
print(f"total distinct regs captured: {len(regs)}")
# dump a few interesting a6xx config registers by offset (dword)
INTEREST = {0x8000:'RB_...',0x88d0:'GRAS_BIN_CONTROL?',0x80a1:'GRAS_BIN_CONTROL',
            0x8804:'RB_BIN_CONTROL',0x8c00:'RB_CCU_CNTL',0x8e07:'RB_UBWC?'}
for o in sorted(regs):
    print(f"  reg 0x{o:05x} = 0x{regs[o]:08x}")
