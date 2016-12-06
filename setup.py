#!/usr/bin/env python

from __future__ import print_function
import os
import sys
from setuptools import setup, find_packages
try:
    import PyQt4
except ImportError:
    print('PyQt4 not found. Please install it first. If using a virtualenv, you '
          'may need to install vext.pyqt4', file=sys.stderr)
    sys.exit(1)

__version__ = "1.3.5"

scripts = [
    'Tigger/bin/tigger-convert',
    'Tigger/bin/tigger-make-brick',
    'Tigger/bin/tigger-restore',
    'Tigger/bin/tigger-tag',
    'Tigger/tigger',
]

package_data = {'Tigger': [
    'icons/*.png',
    'tigger.conf',
] }


setup(
    name = "astro-tigger",
    version = __version__,
    packages = find_packages(),
    scripts = scripts,
    package_data = package_data,
    description = "yet another FITS image viewer",
    author = "Oleg Smirnov",
    author_email = "osmirnov@gmail.com",
    url = "https://github.com/ska-sa/tigger",
    install_requires=['astro_kittens', 'numpy', 'scipy', 'astlib', 'pyfits']
)

