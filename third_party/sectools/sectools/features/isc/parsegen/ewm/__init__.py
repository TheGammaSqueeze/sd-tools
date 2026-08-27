#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from sectools.features.isc.parsegen.ewm.format import SecParseGenEwm
from sectools.features.isc.parsegen.elf_mbn_v6 import ElfMbnV6
from sectools.features.isc.parsegen.elf_mbn_v5 import ElfMbnV5
from sectools.features.isc.parsegen.elf_mbn_v3_encdec import ElfMbnV3EncDec


class EwmV6(SecParseGenEwm, ElfMbnV6):
    """ EWM file type based on ELF-MBN Version 6 """


class EwmV5(SecParseGenEwm, ElfMbnV5):
    """ EWM file type based on ELF-MBN Version 5 """


class EwmV3(SecParseGenEwm, ElfMbnV3EncDec):
    """ EWM file type based on ELF-MBN Version 3 """
