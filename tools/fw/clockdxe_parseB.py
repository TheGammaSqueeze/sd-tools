import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def cstr(o):
    e=o
    while e<N and data[e]!=0: e+=1
    if e-o<2: return None
    s=data[o:e]
    if not all(32<=b<127 for b in s): return None
    return s.decode('ascii')

# what is 0x26358 (the repeated volt-desc)?
print("0x26358 region:")
for o in range(0x26340,0x263a0,8):
    v=rd64(o); s=cstr(v)
    print("  0x%05x: %016x %s"%(o,v,'"%s"'%s if s else ('->0x%x'%v if 0<v<N else '')))

# find string offsets for the GPU pll names near these tables
for kw in ["pll","cc_pll","gpu","cam","disp","video","gpll"]:
    pass
# list all strings that look like clock source names referenced from 0x25000-0x26800 tables
print("\nNames referenced from PLL tables 0x24e00..0x26800:")
seen=set()
for o in range(0x24e00,0x26800,8):
    v=rd64(o); s=cstr(v)
    if s and any(c.isalpha() for c in s) and ('pll' in s or 'clk' in s or 'cc' in s or 'gpll' in s) and v not in seen:
        seen.add(v); print("  @0x%05x ref from 0x%05x: %s"%(v,o,s))
