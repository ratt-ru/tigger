#!/usr/bin/env python

from __future__ import print_function
import os
import sys
from setuptools import setup, find_packages
import warnings

msg = """
Could not detect PyQt4. Install PyQt4 system wide. If you are in
a virtualenv install the vext.pyqt4 package: 

  $ pip install astro-tigger[venv]

"""

try:
    import PyQt4
except ImportError:
    warnings.warn(msg)


__version__ = "1.3.10"

requirements = ['astro_kittens', 'numpy', 'scipy', 'astlib', 'pyfits']

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

extras_require = {
    'venv': ['vext.pyqt4'],
}


setup(
    name ="astro-tigger",
    version=__version__,
    packages=find_packages(),
    extras_require=extras_require,
    scripts=scripts,
    package_data=package_data,
    description="yet another FITS image viewer",
    author="Oleg Smirnov",
    author_email="osmirnov@gmail.com",
    url="https://github.com/ska-sa/tigger",
    install_requires=requirements,
)

