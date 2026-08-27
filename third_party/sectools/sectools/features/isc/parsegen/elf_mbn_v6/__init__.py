#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.base_encdec import SecParseGenBaseEncDec
from .elf_v6 import ElfV6
from .mbn_v6 import MbnV6


class ElfMbnV6(ElfV6, MbnV6, SecParseGenBaseEncDec):
    """ ELF MBN Version 6 Meta Data ParseGen """
