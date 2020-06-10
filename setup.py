#!/usr/bin/env python

from __future__ import print_function
from setuptools import setup, find_packages

__version__ = "1.5.0"

requirements = ['numpy', 'scipy', 'astlib', 'astropy', 'astro_tigger_lsm', 'configparser']

scripts = [
    'TigGUI/tigger',
]

package_data = {'TigGUI': [
        'icons/*.png',
        'tigger.conf',
    ]
}

extras_require = {
    'venv': ['vext.pyqt4'],
}


setup(
    name="astro-tigger",
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

