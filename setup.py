#!/usr/bin/env python

import os
from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES

scripts_dir = "Tigger/bin/"
tigger_scripts = [scripts_dir + i for i in os.listdir(scripts_dir)]


def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join) in a
    platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

# Tell distutils not to put the data_files in platform-specific installation
# locations. See here for an explanation:
# http://groups.google.com/group/comp.lang.python/browse_thread/thread/35ec7b2fed36eaec/2105ee4d9e8042cb
for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']

tigger_packages = []
tigger_data_files = []
root_dir = os.path.dirname(__file__)
if root_dir != '':
    os.chdir(root_dir)

for dirpath, dirnames, filenames in os.walk('Tigger'):
    # Ignore dirnames that start with '.'
    dirnames[:] = [d for d in dirnames if not d.startswith('.') and d != '__pycache__']
    if '__init__.py' in filenames:
        tigger_packages.append('.'.join(fullsplit(dirpath)))
    elif filenames:
        tigger_data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames]])

setup(
    name = "tigger",
    version = "1.3.0",
    packages = tigger_packages,
    scripts = tigger_scripts,
    data_files=tigger_data_files,
    description = "yet another FITS image viewer",
    author = "Oleg Smirnov",
    author_email = "osmirnov@gmail.com",
    url = "https://github.com/ska-sa/tigger",
    requires=['kittens', 'PyQt4', 'numpy' 'astlib'],
)

