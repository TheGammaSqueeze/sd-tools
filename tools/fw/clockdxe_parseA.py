import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
def rd32(o): return struct.unpack_from("<I",data,o)[0]

# Find every 8-byte-aligned position whose value is a known ladder head, print row = arrptr, outfreq(next qword)
ladder_heads={0x16d40,0x17398,0x17648,0x17690,0x17e38,0x17e80,0x17ec8,0x17f10,
 0x181e8,0x18230,0x18278,0x182c0,0x18308,0x18350,0x18398,0x183e0,
 0x16908,0x16950,0x16998,0x168c0}
print("Rows referencing a PLL-cfg array head (arrptr, following-qword=outFreq):")
o=0
rows=[]
while o<N-16:
    v=rd64(o)
    if v in ladder_heads:
        nf=rd64(o+8)
        L=rd32(v+0x1c)
        rows.append((o,v,nf,L))
    o+=8
for o,v,nf,L in rows:
    mhz=nf/1e6 if nf<4e9 else None
    print("  tableoff 0x%05x -> arr 0x%05x  L=%3d  vco=%7.1fMHz  outFreq=%s"%(
        o,v,L,L*19.2, ("%9.3fMHz"%mhz if mhz else "0x%x"%nf)))
