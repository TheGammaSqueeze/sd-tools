#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

import os

DIR_PATH = None

def init():
    global DIR_PATH
    DIR_PATH = os.path.dirname(os.path.abspath(__file__))

