#!/usr/bin/env python3

from __future__ import print_function
from setuptools import setup, find_packages
from pathlib import Path

__version__ = "1.6.1"

# PyQt (5.15.x) has not been added here are it needs to be installed via apt-get instead to support Qwt.
# requirements below do not have versions for upstream packaging processes, but tested and compatible versions are given
requirements = [
    'numpy',  # tested with version >=1.19.4 (<= 1.22.3)
    'scipy',  # tested with versions 1.5.2 for Python 3.6 and >=1.6.2 (<= 1.8.0)
    'astlib',  # tested with version 0.11.6 and 0.11.7
    'astropy',  # tested with 4.1, 4.2 and 5.0.4
    'astro_tigger_lsm==1.7.1',  # PyQt5 version of astro-tigger-lsm
    'configparser',  # tested with version 5.0.1 and 5.2.0
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
    url="https://github.com/ratt-ru/tigger",
    python_requires='>=3.6',
    install_requires=requirements,
    data_files=[
        (f"{Path.home()}/.local/share/applications", ['desktop/tigger.desktop']),
        (f"{Path.home()}/.local/share/icons", ['TigGUI/icons/tigger_logo.png']),
    ],
)

