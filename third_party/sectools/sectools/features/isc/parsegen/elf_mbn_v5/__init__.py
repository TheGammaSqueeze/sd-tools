#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.base_encdec import SecParseGenBaseEncDec

from .elf_v5 import ElfV5
from .mbn_v5 import MbnV5


class ElfMbnV5(ElfV5, MbnV5, SecParseGenBaseEncDec):
    """ ELF MBN Version 5 Multiple-Authority ParseGen """
