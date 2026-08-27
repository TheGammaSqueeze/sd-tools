import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def rd32(o): return struct.unpack_from("<I",data,o)[0]

# Each 0x48-stride PLL config block: u64 freqHz @+0, L-value dword @+0x1c.
# Scan region for blocks: freqHz plausible, +8 == 0x24080, then L at +0x1c.
print("All 0x48-stride Zonda PLL config blocks in 0x16900..0x18400:")
print(" foff      freqHz(MHz)  L(+0x1c)  L*19.2   +8       ")
o=0x16900
found=[]
while o<0x18400:
    f=rd64(o); tag8=rd32(o+8)
    if 100_000<f<4_000_000_000 and tag8==0x24080:
        L=rd32(o+0x1c)
        found.append((o,f,L))
        print("  0x%05x  %9.3f   %3d=0x%02x  %8.1f   %08x"%(o,f/1e6,L,L,L*19.2,tag8))
    o+=8
print("\nCount:",len(found))
