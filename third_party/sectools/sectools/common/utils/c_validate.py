#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

def range_check(name, value, min, max):
    if value > max:
        raise RuntimeError("%r cannot be larger than %d" % (name, max))
    elif value < min:
        raise RuntimeError("%r cannot be less than %d" % (name, min))
