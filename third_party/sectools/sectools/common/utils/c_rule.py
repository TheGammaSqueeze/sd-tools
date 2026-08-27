#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

"""
This module provides a rule base class for components to implement their rules.
"""

import abc

from six import add_metaclass


@add_metaclass(abc.ABCMeta)
class CoreRuleBase(object):
    """
    This is an abstract base class that defines the interface for modules that
    need to implement rules, i.e. configuration rules, feature rules, etc...
    """

    @abc.abstractmethod
    def validate(self, data, data_dict):
        pass
