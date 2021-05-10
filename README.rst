======
Tigger
======

.. image:: https://user-images.githubusercontent.com/7116312/113705452-5ac51d00-96d5-11eb-8087-5d2a8ccad99a.png

Installing Tigger
=================

Ubuntu package
--------------

Enable the KERN repository and install the ``tigger`` package.

From source with Ubuntu 20.04
-----------------------------

Python dependencies
^^^^^^^^^^^^^^^^^^^

* Tigger-LSM v1.7.0 - please go here <https://github.com/ska-sa/tigger-lsm> and install this first.

Automatically installed Python dependencies:

* numpy
* scipy
* astlib
* astropy
* configparser

System dependencies
^^^^^^^^^^^^^^^^^^^

* PyQt 5.14.1 (or 5.15.2)
* Qwt 6.1.4 (or 6.1.5)
* PyQt-Qwt 1.02.02 or greater

These are already present in most Linux distributions. Please note that, this package **does not** use the version of PyQt 5 that is installable from PyPI. In addition, it uses the latest version of PyQt-Qwt from GitHub.

Install from source on Ubuntu 20.04 with installation script
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download the Tigger repository::

    git clone https://github.com/ska-sa/tigger.git

Run the installation script and enter ``sudo`` password when prompted::

    ./install_tigger_ubuntu_20_04.sh

Running Tigger
==============

Run the installed ``tigger`` binary, or search for ``tigger`` from Ubuntu's 'Show Applications' icon in the dock.

Questions or problems
=====================

Open an issue on github

https://github.com/ska-sa/tigger


Travis
======

.. image:: https://travis-ci.org/ska-sa/tigger.svg?branch=master
    :target: https://travis-ci.org/ska-sa/tigger
