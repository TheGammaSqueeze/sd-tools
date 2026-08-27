import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def rd32(o): return struct.unpack_from("<I",data,o)[0]
def cstr(o):
    e=o
    while e<N and data[e]!=0: e+=1
    if e-o<2 or e-o>90: return None
    s=data[o:e]
    if not all(32<=b<127 for b in s): return None
    return s.decode('ascii')

# ladder groups: contiguous 0x48 blocks
heads=[0x181e8, 0x182c0, 0x16908, 0x17e38]
for h in heads:
    # walk backward: is h a head? find refs to h anywhere
    refs=[o for o in range(0,N-8) if rd64(o)==h]
    print("head 0x%05x referenced at: %s"%(h,", ".join("0x%05x"%r for r in refs)))

# Dump the descriptor rows for the whole 0x181e8..0x18398 ladder from the 0x264d0 table
print("\n=== voltage/pll-source table rows 0x264d0..0x26640 (stride 0x30) ===")
o=0x264d0
while o<0x26660:
    arr=rd64(o); freq=rd64(o+8)>>32 if False else rd32(o+8+4) # careful
    # row layout observed: +0 arrayptr, +8 ??, let's print raw 0x30
    vals=[rd64(o+k*8) for k in range(6)]
    aptr=vals[0]
    Lguess=rd32(aptr+0x1c) if 0x16000<=aptr<0x18500 else None
    print("  0x%05x: arr=0x%05x  L=%s  row=%s"%(o,aptr,("%d"%Lguess if Lguess else "-"),
        " ".join("%016x"%v for v in vals[1:4])))
    o+=0x30
