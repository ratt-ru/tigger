======
Tigger
======

Installing Tigger
=================

Ubuntu package
--------------

Enable the
`radio astro launchpad PPA <https://launchpad.net/~radio-astro/+archive/ubuntu/main>`_
and install the python-tigger package.


from pypi or from source
------------------------

requirements:

 * Assorted python packages: PyQt4, PyQwt5, pyfits, numpy, scipy, astLib.
 With the exception of astLib, these are already present in most Linux
 distros.  astLib may be downloaded here: http://astlib.sourceforge.net/

 * Purr/Kittens. Easiest to install the purr package from a MeqTrees binary
 distribution (see http://www.astron.nl/meqwiki/Downloading). Alternatively, 
 check it out from svn (see below), and make sure the parent 
 of the Kittens directory is in your PYTHONPATH.

To obtain on ubuntu you can run::

 $ sudo apt-get install python-kittens python-pyfits python-astlib python-scipy python-numpy python-qt4 python-qwt5-qt4 libicu48

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
