#!/usr/bin/env python

from __future__ import print_function
from setuptools import setup, find_packages

__version__ = "1.5.0"

requirements = [
    'numpy>=1.17',
    'scipy>=1.5.2',
    'astlib>=0.10.2',
    'astropy==4.1',
    'astro_tigger_lsm==1.7.0',
    'configparser>=5.0.1',
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
)

