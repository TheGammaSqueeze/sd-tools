#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.base_encdec import SecParseGenBaseEncDec

from .elf_v3_licmngr import ElfV3Licmngr
from ..elf_mbn_v3_encdec.mbn_v3_encdec import MbnV3EncDec


class ElfMbnV3Licmngr(ElfV3Licmngr, MbnV3EncDec, SecParseGenBaseEncDec):
    """ ELF MBN Version 3 License Manager ParseGen """
