#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

import hashlib

from six import ensure_binary

from sectools.common.crypto.functions.utils import UtilsBase


class UtilsOpenSSLImpl(UtilsBase):

    hash_algos_map = {
        UtilsBase.HASH_ALGO_SHA1: hashlib.sha1,
        UtilsBase.HASH_ALGO_SHA256: hashlib.sha256,
        UtilsBase.HASH_ALGO_SHA384: hashlib.sha384
    }

    def __init__(self, module):
        super(UtilsOpenSSLImpl, self).__init__(module)
        self.openssl = module

    def hash(self, message, hash_algo):
        message = ensure_binary(message)

        if hash_algo in self.hash_algos_map.keys():
            return self.hash_algos_map[hash_algo](message).hexdigest()
        else:
            return hashlib.sha256(message).hexdigest()
