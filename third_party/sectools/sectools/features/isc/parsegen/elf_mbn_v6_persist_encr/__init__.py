#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.base_encdec import SecParseGenBaseEncDec
from .elf_v6_persist_encr import ElfV6PersistEncr
from .mbn_v6_persist_encr import MbnV6PersistEncr

class ElfMbnV6PersistEncr(ElfV6PersistEncr, MbnV6PersistEncr, SecParseGenBaseEncDec):
    """ ELF MBN Version 6 For SPU images to sign without decrypting """
