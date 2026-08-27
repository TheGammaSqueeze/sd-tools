import pefile, struct, sys

PATH = "/work/sd-tools/modified/uefi_ext/fv.bin_output/volume-0/file-9e21fd93-9c72-4c15-8c4b-e77f1db2d792/section0/section1/volume-1d301fe9-be79-4353-91c2-d23bc959ae0c/file-4db5dea6-5302-4d1a-8a82-677a683b0d29/section1.pe"

data = open(PATH,"rb").read()
pe = pefile.PE(data=PATH, fast_load=False) if False else pefile.PE(PATH)

ib = pe.OPTIONAL_HEADER.ImageBase
print("ImageBase = 0x%x" % ib)
print("Machine   = 0x%x" % pe.FILE_HEADER.Machine)
print("Subsystem = 0x%x" % pe.OPTIONAL_HEADER.Subsystem)
print("EntryRVA  = 0x%x" % pe.OPTIONAL_HEADER.AddressOfEntryPoint)
print("Sections:")
secs=[]
for s in pe.sections:
    name=s.Name.rstrip(b'\x00').decode('latin1')
    print("  %-8s VA=0x%08x VSize=0x%06x RawPtr=0x%06x RawSize=0x%06x flags=0x%x"%(
        name, s.VirtualAddress, s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData, s.Characteristics))
    secs.append((name, s.VirtualAddress, s.Misc_VirtualSize, s.PointerToRawData, s.SizeOfRawData))

def foff_to_rva(fo):
    for name,va,vs,rp,rs in secs:
        if rp<=fo<rp+rs:
            return va+(fo-rp)
    return None
def rva_to_foff(rva):
    for name,va,vs,rp,rs in secs:
        if va<=rva<va+max(vs,rs):
            return rp+(rva-va)
    return None
def va_to_foff(va):
    return rva_to_foff(va-ib)

print("\n-- map check --")
for fo in [0x16950,0x16998,0x182c0,0x18308,0x18350,0x18398]:
    rva=foff_to_rva(fo); print("  foff 0x%05x -> rva 0x%05x -> va 0x%x"%(fo,rva,ib+rva))

# freq array region VA range
lo_fo, hi_fo = 0x16900, 0x18400
lo_va = ib+foff_to_rva(lo_fo); hi_va = ib+foff_to_rva(hi_fo)
print("\nfreq region VA range: 0x%x .. 0x%x"%(lo_va,hi_va))

# scan whole file for 8-byte LE values that equal a pointer VA into freq region
print("\n-- scan for pointers into freq region --")
hits=[]
for off in range(0, len(data)-8):
    v=struct.unpack_from("<Q", data, off)[0]
    if lo_va<=v<=hi_va:
        tgt_fo=va_to_foff(v)
        hits.append((off,v,tgt_fo))
for off,v,tgt in hits:
    print("  ptr at foff 0x%05x -> VA 0x%x (freq foff 0x%05x)"%(off,v,tgt))
