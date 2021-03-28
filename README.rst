======
Tigger
======

Installing Tigger
=================

Ubuntu package
--------------

Enable the KERN repository and install the `tigger` package.

from source with Ubuntu 20.04
------------------------------

System dependencies: PyQt 5.14.1 (or 5.15), PyQt-Qwt and Qwt6.1.4 (or 6.1.5). These are already present in most Linux distributions.

Please note that, this package **does not** use the version of PyQt 5 that is installable from PyPI.

To install the system dependencies on Ubuntu 20.04 you can run::

 $ sudo apt install python3-pyqt5.qwt python3-pyqt5.qtsvg python3-pyqt5.qtopengl

Then build the source::

    $ git clone https://github.com/razman786/tigger_py5.git
    $ cd tigger_py5
    $ python3 setup.py install


Running Tigger
==============

Run the installed `tigger` binary.

Questions or problems
=====================

Open an issue on github

https://github.com/ska-sa/tigger

Travis
======

.. image:: https://travis-ci.org/ska-sa/tigger.svg?branch=master
    :target: https://travis-ci.org/ska-sa/tigger
