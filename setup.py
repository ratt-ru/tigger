#!/usr/bin/env python

from __future__ import print_function
from setuptools import setup, find_packages
from pathlib import Path

__version__ = "1.5.0"

# PyQt has not been added here are it needs to be installed via apt-get instead to support Qwt.
# Versions below are set to astLib 0.11.6 tested and compatible versions found
requirements = [
    'numpy==1.18.1',  # set to astLib recommended
    'scipy==1.5.2',  # recommends 1.3.1, this fails, next available version
    'astlib==0.11.6',  # latest version that uses astropy WCS at the backend
    'astropy==3.2.3',  # recommends 3.2.1, this fails, next available version (last of 3.x)
    'astro_tigger_lsm==1.7.0',  # PyQt5 version of astro-tigger-lsm
    'configparser==5.0.1',
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
    install_requires=requirements,
    data_files=[
        (f"{Path.home()}/.local/share/applications", ['desktop/tigger.desktop']),
        (f"{Path.home()}/.local/share/icons", ['TigGUI/icons/tigger_logo.png']),
    ],
)

