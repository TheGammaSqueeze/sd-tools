#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.base import SecParseGenBase

from .mbn_v3_base import MbnV3Base
from .elf_v3_base import ElfV3Base


class ElfMbnV3Base(ElfV3Base, MbnV3Base, SecParseGenBase):
    """ ELF MBN Version 3 Base ParseGen """
