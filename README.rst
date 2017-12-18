======
Tigger
======

Installing Tigger
=================

Ubuntu package
--------------

Enable the KERN repository and install the tigger package.


from pypi or from source
------------------------

Requirements: PyQt4, PyQwt5. These are already present in most Linux distros.

To obtain on ubuntu you can run::

 $ sudo apt-get install python-qt4 python-qwt5-qt4 libicu48

now from pip::

    $ pip install astro-tigger

or from source::

    $ git clone https://github.com/ska-sa/tigger
    $ cd tigger
    $ python setup.py install


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
