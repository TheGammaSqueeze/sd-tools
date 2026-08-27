import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]

# find all C strings with clock-domain keywords
kw=[b"perfcl",b"pwrcl",b"l3_clk",b"cpuss",b"apss",b"apcs",b"cpu_",b"_cpu",b"gold",b"silver",b"prime",b"zonda",b"kryo",b"acd",b"gpll0",b"cluster",b"apc"]
strs={}
i=0
while i<N:
    if 32<=data[i]<127:
        j=i
        while j<N and 32<=data[j]<127: j+=1
        if j-i>=3 and data[j:j+1]==b'\x00':
            s=data[i:j]
            strs[i]=s
        i=j
    else: i+=1

hits={o:s for o,s in strs.items() if any(k in s.lower() for k in kw)}
print("=== clock-domain-name strings ===")
for o in sorted(hits): print("  0x%05x: %s"%(o,hits[o].decode('ascii','replace')))

# for each such string offset, find 64-bit pointers to it (descriptor name fields)
print("\n=== references to those name strings (name-field of descriptors) ===")
ptrmap={}
for o in range(0,N-8):
    v=rd64(o)
    if v in hits:
        ptrmap.setdefault(v,[]).append(o)
for v in sorted(ptrmap):
    print("  name '%s' (@0x%05x) referenced at: %s"%(hits[v].decode(),v,", ".join("0x%05x"%x for x in ptrmap[v])))
