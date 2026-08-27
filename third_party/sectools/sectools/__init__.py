#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================


# Name & version of the tool
SECTOOLS_TOOL_NAME = 'SecTools'
SECTOOLS_TOOL_VERSION = '5.74'

import os
import sys

# Add any external modules to the path. Add  to the beginning of the syspath so
# ext modules override any already in the syspath. Note we are inserting at
# position 1, since position 0 is assumed to be the path to the sectools dir.
CUR_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.abspath(os.path.join(CUR_DIR, '..', 'ext')))

# c_misc needs to be imported to ensure subprocess.check_output method exists
from sectools.common.utils import c_misc


class Paths(object):
    """ Contains common paths used throughout the tool """
    TopLevel = os.path.dirname(CUR_DIR)
    SecToolsPy = os.path.join(os.path.dirname(CUR_DIR), "sectools.py")
