#!/usr/bin/env python

from setuptools import setup, find_packages

__version__ = "1.4.0"

install_requires = [
    'astro_kittens',
    'numpy',
    'scipy',
    'astlib',
    'astropy',
    'pyqt5',
]

scripts = [
    'Tigger/bin/tigger-convert',
    'Tigger/bin/tigger-make-brick',
    'Tigger/bin/tigger-restore',
    'Tigger/bin/tigger-tag',
    'Tigger/tigger',
]

package_data = {
    'Tigger': [
        'icons/*.png',
        'tigger.conf',
    ]
}


setup(
    name ="astro-tigger",
    version=__version__,
    packages=find_packages(),
    scripts=scripts,
    package_data=package_data,
    description="yet another FITS image viewer",
    author="Oleg Smirnov",
    author_email="osmirnov@gmail.com",
    url="https://github.com/ska-sa/tigger",
    install_requires=install_requires,
)

