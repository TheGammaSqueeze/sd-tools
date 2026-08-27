#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

import os
import sys
from glob import glob

from sectools.common.core.plugin import SecPluginMgr


# API to get a signer
def get_signer(config):
    s = signer_mgr.get_signer(config.general_properties.selected_signer)
    return s(config)


class SignerMgr(SecPluginMgr):
    def get_signer(self, signer_id):
        s = self.get_map()
        if signer_id not in s:
            raise RuntimeError(
                'Signer unavailable for signer id: ' + str(signer_id) + '\n' +
                '    ' + 'Available signer ids are: ' + str(s.keys()))
        return s[signer_id]


signer_mgr = SignerMgr()

# Import all the signers
for py_file_name in glob(os.path.join(os.path.dirname(__file__), "*.py")):
    module_name = os.path.splitext(os.path.basename(py_file_name))[0]
    if module_name in ["__init__"]:
        continue
    if hasattr(sys.modules[__name__], module_name):
        continue
    __import__(".".join([__name__, module_name]))

try:
    from plugin import signer
except ImportError:
    signer = None

# Set the signers in the config file
try:
    from sectools.features.isc.cfgparser import defines

    defines.set_signers(signer_mgr.get_map().keys())
except Exception as e:
    signers = []
