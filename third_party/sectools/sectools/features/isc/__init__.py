#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================
"""
:Authors: sectools

Main interface to the secimage functionalities. Supports APIs for
command line interface, UI interface and test interface.
"""

import os

DIR_PATH = os.path.dirname(os.path.abspath(__file__))

# sectools feature candidate lists, to be populated during run-time.
__sectools_features__ = []

for module_name in os.listdir(DIR_PATH):
    if not os.path.isdir(os.path.join(DIR_PATH, module_name)):
        continue
    __sectools_features__.append(module_name)


#------------------------------------------------------------------------------
# Restrict all import
#------------------------------------------------------------------------------
__all__ = ['cfgparser',
           'parsegen',
           ]

