======
Tigger
======

N.B THIS README IS THE BETA TESTER VERSION
==========================================

.. image:: https://user-images.githubusercontent.com/7116312/113705452-5ac51d00-96d5-11eb-8087-5d2a8ccad99a.png

Installing Tigger
=================

From source with Ubuntu
-----------------------
Python dependencies
-------------------
* Tigger-LSM v1.7.0 - please go here <https://github.com/razman786/tigger_lsm_pyqt5> and install this first.

Automatically installed Python dependencies:

* numpy >= v1.17
* scipy == v1.5.2
* astlib == v0.10.2
* astropy == v4.1
* configparser == v5.0.1

System dependencies
-------------------

* PyQt 5.14.1 (or 5.15.x)
* Qwt 6.1.4 (or 6.1.5)
* PyQt-Qwt 1.02.00

These are already present in most Linux distributions. Please note that, this package **does not** use the version of PyQt 5 that is installable from PyPI.

Install from source on Ubuntu 20.04
-----------------------------------

To install the system dependencies on Ubuntu 20.04 you can run::

    sudo apt install python3-pyqt5.qwt python3-pyqt5.qtsvg python3-pyqt5.qtopengl

Then build the source::

    git clone https://github.com/razman786/tigger_py5.git
    cd tigger_py5
    python3 setup.py install --user

Install from source on Ubuntu 18.04
-----------------------------------

To install on Ubuntu 18.04, first clone the repository::

    git clone https://github.com/razman786/tigger_py5.git

Install the Ubuntu 18.04 Qwt Pyhton 3 pacakge::

    cd tigger_py5/ubuntu_bionic_deb_pkg
    sudo dpkg -i python3-pyqt5.qwt_1.00.00-1_amd64.deb
    sudo apt -f install
    sudo apt install python3-pyqt5.qtsvg python3-pyqt5.qtopengl
    cd ..
    python3 setup.py install --user

Running Tigger
==============

Run the installed ``tigger`` binary, or search for `tigger` from Ubuntu's 'Show Applications' icon in the dock.

Beta Tester Questions or problems
=================================

Open an issue on this github:

https://github.com/razman786/tigger_py5/issues

Travis
======

.. image:: https://travis-ci.org/ska-sa/tigger.svg?branch=master
    :target: https://travis-ci.org/ska-sa/tigger
