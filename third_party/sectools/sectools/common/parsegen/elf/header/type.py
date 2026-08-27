#===============================================================================
# Copyright (c) 2024 Qualcomm Innovation Center, Inc. All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#===============================================================================

#------------------------------------------------------------------------------
# ELF HEADER - Type (e_type)
#------------------------------------------------------------------------------
ET_NONE         = 0
ET_REL          = 1
ET_EXEC         = 2
ET_DYN          = 3
ET_CORE         = 4

ET_STRING       = 'Type'
ET_DESCRIPTION = \
{
    ET_NONE     : 'NONE (No file type)',
    ET_REL      : 'REL (Relocatable file)',
    ET_EXEC     : 'EXEC (Executable file)',
    ET_DYN      : 'DYN (Shared object file)',
    ET_CORE     : 'CORE (Core file)',
}
