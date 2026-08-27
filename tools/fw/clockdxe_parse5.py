import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def rd32(o): return struct.unpack_from("<I",data,o)[0]
def cstr(o):
    if not(0<o<N): return None
    e=o
    while e<N and data[e]!=0: e+=1
    if e-o<2 or e-o>80: return None
    s=data[o:e]
    if not all(32<=b<127 for b in s): return None
    return s.decode('ascii')

def row(o):
    a,b=rd64(o),rd64(o+8)
    def ann(v):
        s=cstr(v)
        if s: return '"%s"'%s
        if 0x16000<=v<0x18500: return 'FREQARR@0x%x'%v
        if 0<v<N: return '->0x%x'%v
        return '0x%x'%v if v>0x100000 else str(v)
    return "0x%05x: %016x %016x | %s | %s"%(o,a,b,ann(a),ann(b))

print("=== apcs_*_post_acd_clk descriptor table 0x1a2a0..0x1a340 ===")
for o in range(0x1a2a0,0x1a340,16): print("  "+row(o))

# The descriptor at 0x1a2b8: name ptr is field. The struct likely: {char* name; void* array; UINT32 count; ...}
# Let's dump wider struct starting at each name-ptr location minus offset guesses.
for nameoff,label in [(0x1a2b8,"silver"),(0x1a2c8,"gold"),(0x1a2d8,"l3")]:
    print("\n=== descriptor for %s (name-ptr field @0x%05x) surrounding 0x60 ==="%(label,nameoff))
    base=nameoff-0x20
    for o in range(base,nameoff+0x40,8):
        v=rd64(o); s=cstr(v)
        tag=''
        if s: tag='"%s"'%s
        elif 0x16000<=v<0x18500: tag='FREQARR@0x%x'%v
        elif 0<v<N: tag='->0x%x'%v
        mark=' <== name' if o==nameoff else ''
        print("    0x%05x: %016x  %s%s"%(o,v,tag,mark))
