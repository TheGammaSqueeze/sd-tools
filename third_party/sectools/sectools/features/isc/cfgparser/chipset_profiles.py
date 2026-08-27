#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

class ChipsetProfile(object):

    def __init__(self, secboot_version, in_use_soc_hw_version, msm_part,
                 soc_vers, soc_hw_version, platform_independent):
        self.secboot_version = secboot_version
        self.in_use_soc_hw_version = in_use_soc_hw_version
        self.msm_part = msm_part
        self.soc_vers = soc_vers if soc_vers else []
        self.soc_hw_version = soc_hw_version
        self.platform_independent = platform_independent


CHIPSET_PROFILES = {
    "qcc730": {
        "msm_part": [
            "0x0029F0E1"
        ]
    },
}
