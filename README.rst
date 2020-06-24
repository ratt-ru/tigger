======
Tigger
======

Installing Tigger
=================

Ubuntu package
--------------

N/A

from source with Ubuntu 19.10+
------------------------------

Requirements: PyQt5, PyQwt6. These are already present in most Linux distros.

To install on Ubuntu 19.10 to 20.04 you can run::

 $ sudo apt install python3-pyqt5.qwt python3-pyqt5.qtsvg

Then build the source::

    $ git clone https://github.com/razman786/tigger_py5.git
    $ cd tigger_py5
    $ python3 setup.py install

from source with Ubuntu 18.04
-----------------------------

Requirements: PyQt5, PyQwt6. These are already present in most Linux distros.

To install on Ubuntu 18.04, first clone the repository::

    $ git clone https://github.com/razman786/tigger_py5.git

Install the Ubuntu 18.04 Qwt Pyhton 3 pacakge::

    $ cd tigger_py5/ubuntu_bionic_deb_pkg
    $ sudo dpkg -i python3-pyqt5.qwt_1.00.00-1_amd64.deb
    $ sudo apt -f install
    $ sudo apt install python3-pyqt5.qtsvg
    $ cd ..
    $ python3 setup.py install

Running Tigger
==============

Run the installed tigger binary.


Questions or problems
=====================

Open an issue on github

https://github.com/ska-sa/tigger


Travis
======

.. image:: https://travis-ci.org/ska-sa/tigger.svg?branch=master
    :target: https://travis-ci.org/ska-sa/tigger
