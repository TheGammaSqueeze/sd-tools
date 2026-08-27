import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def rd32(o): return struct.unpack_from("<I",data,o)[0]
def cstr(o):
    if not(0<o<N): return None
    e=o
    while e<N and data[e]!=0: e+=1
    if e-o<2 or e-o>90: return None
    s=data[o:e]
    if not all(32<=b<127 for b in s): return None
    return s.decode('ascii')
def ann(v):
    s=cstr(v)
    if s: return '"%s"'%s
    if 0x16000<=v<0x18500: return 'FREQARR@0x%x'%v
    if 0<v<N: return '->0x%x'%v
    return '0x%x'%v if v>0x100000 else str(v)

for base,lbl in [(0x24ee0,"@0x24f58 grp (16908/16950/16998)"),(0x25180,"@0x251a0 gcc_gpll0")]:
    print("=== %s : dump 0x%05x..+0xa0 ==="%(lbl,base))
    for o in range(base,base+0xa0,8):
        v=rd64(o)
        print("  0x%05x: %016x  %s"%(o,v,ann(v)))
    print()
