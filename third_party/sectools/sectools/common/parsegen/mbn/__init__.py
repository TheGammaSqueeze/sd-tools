#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

# used to get MBN header object for all MBN header versions
get_header = {}

"""
Map of: (MbnHeaderSize, MbnHeaderVersion) -> Mbn Header Class

Dictionary containing a mapping of the class to use for parsing the MBN header
based on the header type specified
"""
MBN_HDRS = {}
