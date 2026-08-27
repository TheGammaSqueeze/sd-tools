#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.base_encdec import SecParseGenBaseEncDec
from ..elf_mbn_v6.mbn_v6 import MbnV6
from .elf_v6_multi_image import ElfV6MultiImage


class ElfMbnV6MultiImage(ElfV6MultiImage, MbnV6, SecParseGenBaseEncDec):
    """ ELF MBN Version 6 Multi-image ParseGen """
