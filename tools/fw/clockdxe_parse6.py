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

for desc,label in [(0x272ac,"silver"),(0x273f4,"gold"),(0x2753c,"l3")]:
    print("\n=== %s domain desc @0x%05x (dump 0x60) ==="%(label,desc))
    for o in range(desc,desc+0x60,8):
        v=rd64(o); s=cstr(v)
        tag=''
        if s: tag='"%s"'%s
        elif 0x16000<=v<0x18500: tag='FREQARR@0x%x'%v
        elif 0<v<N: tag='->0x%x'%v
        # also show as two dwords
        lo=rd32(o); hi=rd32(o+4)
        print("    +0x%02x 0x%05x: %016x (%08x %08x) %s"%(o-desc,o,v,lo,hi,tag))
