import struct
PATH="/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"
data=open(PATH,"rb").read(); N=len(data)
def rd64(o): return struct.unpack_from("<Q",data,o)[0]
# any u64 in whole file equal to canonical CPU freqs? 2200MHz,2000MHz etc
targets={2200000000:"2.2GHz",2000000000:"2.0GHz",2100000000:"2.1GHz",1804800000:"1.8G",
2016000000:"2016",2419200000:"2.4G",2246400000:"2246"}
print("Search whole file for canonical CPU freq u64 values:")
for o in range(0,N-8,4):
    v=rd64(o)
    if v in targets: print("  0x%05x = %s"%(o,targets[v]))
# also check apss_cc descriptor at 0x227e0
print("\napss_cc descriptor context 0x227c0..0x22860:")
def cstr(o):
    e=o
    while e<N and data[e]!=0:e+=1
    if e-o<2 or e-o>60:return None
    s=data[o:e]
    return s.decode('ascii') if all(32<=b<127 for b in s) else None
for o in range(0x227c0,0x22860,8):
    v=rd64(o); s=cstr(v)
    print("  0x%05x: %016x %s"%(o,v,'"%s"'%s if s else('->0x%x'%v if 0<v<N else '')))
print("\nDone.")
