#!/usr/bin/env python

import os
from setuptools import setup, find_packages

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
    requires=['astro_kittens', 'PyQt4', 'numpy', 'astlib'],
)

