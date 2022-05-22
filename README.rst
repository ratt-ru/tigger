======
Tigger
======

|actionsbadge| |actionspypibadge| |versionbadge|

.. |actionsbadge| image:: https://github.com/ratt-ru/tigger/workflows/Tigger%20Ubuntu%20CI/badge.svg
    :target: https://github.com/ratt-ru/tigger/actions
.. |actionspypibadge| image:: https://github.com/ratt-ru/tigger/workflows/Deploy%20Python%20Package/badge.svg
    :target: https://github.com/ratt-ru/tigger/actions
.. |versionbadge| image:: https://img.shields.io/github/v/release/ratt-ru/tigger
    :target: https://github.com/ratt-ru/tigger/releases
    :alt: GitHub release (latest by date)

.. image:: https://user-images.githubusercontent.com/7116312/113705452-5ac51d00-96d5-11eb-8087-5d2a8ccad99a.png

Installing Tigger
=================

Ubuntu package
--------------

Enable the KERN repository <https://kernsuite.info> and install the ``tigger`` package.

From source with Ubuntu LTS
---------------------------

Python dependencies
^^^^^^^^^^^^^^^^^^^

* Tigger-LSM v1.7.1 - if you are not installing Tigger via the KERN repository or using the ``install_tigger_ubuntu.sh`` script provided, please go here <https://github.com/ratt-ru/tigger-lsm> and install this first.

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
* PyQt-Qwt 1.9.0 (or greater)

These are already present in most Linux distributions. Please note that, this package **does not** use the version of PyQt 5 that is installable from PyPI. Tigger also uses a version of PyQt-Qwt from GitHub.

Install on Ubuntu LTS with the installation script
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download the Tigger repository::

    git clone https://github.com/ratt-ru/tigger.git

The installation script works on Ubuntu 18.04, 20.04 and 22.04 (including ARM64).

Run the installation script and enter ``sudo`` password when prompted::

    ./install_tigger_ubuntu.sh

Manual installation from source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After the Tigger repository has been downloaded with ``git clone https://github.com/ratt-ru/tigger.git``, please run the following::

    sudo apt -y install python3-pyqt5.qtsvg python3-pyqt5.qtopengl libqwt-qt5-6
    sudo dpkg -i debian_pkgs/ubuntu_22_04_deb_pkg/python3-pyqt5.qwt_2.00.00-1build1_amd64.deb
    pip3 install . --user

Please note that the above commands are for installing on Ubuntu 22.04, Debian packages for 18.04, 20.04 and 22.04 ARM64 are located in the ``ubuntu_18_04_deb_pkg``, ``ubuntu_20_04_deb_pkg`` and ``ubuntu_20_04__arm64_deb_pkg`` directories respectively.

Running Tigger
==============

Run the installed ``tigger`` binary, or search for ``tigger`` from Ubuntu's 'Show Applications' icon in the dock (after logging off and on again).

Questions or problems
=====================

Open an issue on github

https://github.com/ratt-ru/tigger/issues

Contributors
============

Thank you to the people who have contributed to this project.

.. image:: https://contrib.rocks/image?repo=ratt-ru/tigger
    :target: https://github.com/ratt-ru/tigger/graphs/contributors

