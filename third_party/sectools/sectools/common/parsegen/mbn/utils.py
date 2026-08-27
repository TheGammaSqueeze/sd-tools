#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

def extract_segment(data, offset, size):
    seg = ''
    if 0 < offset < len(data) and size > 0:
        seg = data[offset: offset + size]
        data = data[: offset]
    return data, seg


class _BackupMbnParsegen(object):

    def __init__(self, parsegen, *attributes):
        self.backup(parsegen, *attributes)

    def clear_attributes(self, parsegen, *attributes):
        for attr in attributes:
            setattr(parsegen, attr, '')

    def backup_attributes(self, parsegen, *attributes):
        for attr in attributes:
            if hasattr(parsegen, attr):
                setattr(self, attr, getattr(parsegen, attr))

    def restore_attributes(self, parsegen, *attributes):
        for attr in attributes:
            if hasattr(self, attr):
                setattr(parsegen, attr, getattr(self, attr))

    def backup(self, parsegen, *attributes):
        self.backup_attributes(parsegen, *attributes)
        self.clear_attributes(parsegen, *attributes)
        return parsegen

    def restore(self, parsegen, *attributes):
        self.restore_attributes(parsegen, *attributes)
        self.clear_attributes(self, *attributes)
        return parsegen
