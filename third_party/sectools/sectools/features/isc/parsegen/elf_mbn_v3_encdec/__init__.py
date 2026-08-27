#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.base_encdec import SecParseGenBaseEncDec

from .elf_v3_encdec import ElfV3EncDec
from .mbn_v3_encdec import MbnV3EncDec


class ElfMbnV3EncDec(ElfV3EncDec, MbnV3EncDec, SecParseGenBaseEncDec):
    """ ELF MBN Version 3 with Encryption and Decryption """

