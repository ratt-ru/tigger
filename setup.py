#!/usr/bin/env python

from __future__ import print_function
import os
import sys
from setuptools import setup, find_packages
import warnings

requirements = ['astro_kittens', 'numpy', 'scipy', 'astlib', 'pyfits']
try:
    import PyQt4
except ImportError:
    if hasattr(sys, 'real_prefix'):
        warnings.warn('Could not detect PyQt4, but we detected a virtual environment.'
                      ' Will proceed with vext.pyqt4. If errors occur, please '
                      'install PyQt4')
        requirements.append('vext.pyqt4')
    else:
        raise ImportError('PyQt4 not found. Please install it first. If using a virtualenv, you '
          'may need to install vext.pyqt4')

__version__ = "1.3.9"

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
    install_requires=requirements,
)

