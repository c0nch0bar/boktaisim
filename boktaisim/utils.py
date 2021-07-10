#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys


def get_state():
    if sys.platform == 'darwin':
        system = 'mac'
    elif sys.platform == 'win32':
        system = 'windows'
    else:
        system = 'linux'
    if hasattr(sys, 'frozen'):
        state = 'frozen'
        if sys.frozen == 'macosx_app':
            package = 'app'
        elif sys.frozen == 'windows_exe':
            package = 'exe'
        else:
            package = 'bin'
    else:
        state = 'thawed'
        package = 'none'

    return system, state, package
