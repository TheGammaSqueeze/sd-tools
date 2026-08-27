import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def rd32(o): return struct.unpack_from("<I",data,o)[0]
def cstr(o):
    if not(0<o<N): return None
    e=o
    while e<N and data[e]!=0: e+=1
    if e-o<2: return None
    s=data[o:e]
    if not all(32<=b<127 for b in s): return None
    return s.decode('ascii')

# Array heads of interest (the confirmed CPU-range group). Each freq-config array starts at some head.
# The group 0x182c0.. entries are elements. The ARRAY HEAD referenced by a descriptor is likely the
# first element = 0x182c0? but 0x26580 ptr -> 0x182c0. Let's look at descriptor context around 0x26580.
print("=== descriptor context 0x26400..0x26680 (16-byte rows) ===")
o=0x26400
while o<0x26680:
    vals=[rd64(o+k*8) for k in range(2)]
    ann=[]
    for v in vals:
        s=cstr(v)
        if s: ann.append('"%s"'%s)
        elif 0x16000<v<0x18500: ann.append('ARR@0x%x'%v)
        elif 0<v<N: ann.append('->0x%x'%v)
        else: ann.append('%d'%v if v<0x100000 else '0x%x'%v)
    print("  0x%05x: %-18s %-18s | %s"%(o,'%016x'%vals[0],'%016x'%vals[1],'  '.join(ann)))
    o+=16
