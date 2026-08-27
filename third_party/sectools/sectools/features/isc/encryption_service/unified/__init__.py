#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

from . import encdec
# Import built-in encrypted key providers
from sectools.features.isc.encryption_service.unified.encrypted_key_provider import ServerEncryptedKeyProvider

# Try to import oem-defined encrypted key providers
try:
    from plugin import encrypted_key_provider
except ImportError:
    pass
