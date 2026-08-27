#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

import os
import sys

from . import v3

mbn_versions_path = os.path.realpath(os.path.dirname(__file__))

for module_name in os.listdir(mbn_versions_path):
    if not os.path.isdir(os.path.join(mbn_versions_path, module_name)):
        continue

    if hasattr(sys.modules[__name__], module_name):
        continue

    if module_name in ['__pycache__']:
        continue

    __import__(".".join([__name__, module_name]))
