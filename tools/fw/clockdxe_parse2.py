import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read()
N=len(data)

def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def rd32(o): return struct.unpack_from("<I",data,o)[0]
def is_ptr(v): return 0<v<N
def cstr(o):
    if not (0<o<N): return None
    e=o
    while e<N and data[e]!=0: e+=1
    s=data[o:e]
    try: t=s.decode('ascii')
    except: return None
    if len(t)<2 or not all(32<=b<127 for b in s): return None
    return t

# Decode a freq-config array at foff. Struct: u64 freqHz, then config dwords. Determine stride by scanning.
def dump_arr(foff, count=40, stride=0x48):
    print("  array @0x%05x stride 0x%x:"%(foff,stride))
    for i in range(count):
        o=foff+i*stride
        if o+8>N: break
        f=rd64(o)
        if f==0:
            print("    [%2d] @0x%05x freq=0 (terminator?)"%(i,o)); break
        if f>4_000_000_000 or f<100_000: 
            print("    [%2d] @0x%05x non-freq 0x%x -- stop"%(i,o,f)); break
        cfg=rd32(o+8); cfg2=rd32(o+12); cfg3=rd32(o+16)
        L=f/19200000.0
        print("    [%2d] @0x%05x %8.3f MHz  L=%6.2f  +8=0x%08x +12=0x%08x +16=0x%08x"%(i,o,f/1e6,L,cfg,cfg2,cfg3))

# First, figure out actual stride for the 0x182c0 group by dumping raw
print("=== raw hexdump 0x182c0..0x183e0 (u64 freq + dwords) ===")
o=0x182c0
while o<0x18400:
    print("  0x%05x: %016x  %08x %08x %08x %08x"%(o,rd64(o),rd32(o+8),rd32(o+12),rd32(o+16),rd32(o+20)))
    o+=8

print("\n=== raw 0x16950..0x169e0 ===")
o=0x16950
while o<0x169e0:
    print("  0x%05x: %016x  %08x %08x %08x"%(o,rd64(o),rd32(o+8),rd32(o+12),rd32(o+16)))
    o+=8
