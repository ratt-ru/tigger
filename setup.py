#!/usr/bin/env python

from __future__ import print_function
from setuptools import setup, find_packages
from pathlib import Path

__version__ = "1.6.0"

# PyQt (5.15.x) has not been added here are it needs to be installed via apt-get instead to support Qwt.
# requirements below do not have versions for upstream packaging processes, but tested and compatible versions are given
requirements = [
    'numpy',  # tested with version >=1.19.4
    'scipy',  # tested with versions 1.5.2 for Python 3.6 and >=1.6.2
    'astlib',  # tested with version 0.11.6
    'astropy',  # tested with 4.1 and 4.2
    'astro_tigger_lsm==1.7.0',  # PyQt5 version of astro-tigger-lsm
    'configparser',  # tested with version 5.0.1
]

scripts = [
    'TigGUI/tigger',
]

package_data = {'TigGUI': [
        'icons/*.png',
        'tigger.conf',
    ]
}


setup(
    name="astro-tigger",
    version=__version__,
    packages=find_packages(),
    scripts=scripts,
    package_data=package_data,
    description="yet another FITS image viewer",
    author="Oleg Smirnov",
    author_email="osmirnov@gmail.com",
    url="https://github.com/ska-sa/tigger",
    python_requires='>=3.6',
    install_requires=requirements,
    data_files=[
        (f"{Path.home()}/.local/share/applications", ['desktop/tigger.desktop']),
        (f"{Path.home()}/.local/share/icons", ['TigGUI/icons/tigger_logo.png']),
    ],
)

