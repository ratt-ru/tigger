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

    $ git clone https://github.com/ska-sa/tigger
    $ cd tigger
    $ python setup.py install


from source with Ubuntu 18.04
-----------------------------

**Warning the following process involves installing packages from 19.10, which could have unknown side effects.**

With `sudo` create a file `/etc/apt/apt.conf.d/01ubuntu` and within place the following::

    $ APT::Default-Release "bionic";

With `sudo` create a file `/etc/apt/preferences.d/eoan.pref` and within place the following:

```
Package: *
Pin: release n=eoan
Pin-Priority: -10
```

Create a new apt `sources.list` file::

    $ sudo cp /etc/apt/sources.list /etc/apt/sources.list.d/eoan.list

With `sudo` edit `/etc/apt/sources.list.d/eoan.list` and replace all instances of `bionic` with `eoan`. For example with `vim /etc/apt/sources.list.d/eoan.list`::

    $ :%s/bionic/eoan/g

Update `apt` using::

    $ sudo apt update

Check package policy's using::

    $ apt-cache policy

Verify package policy: 

All `eoan` package repoistories should be listed like the following example:

```
-10 http://gb.archive.ubuntu.com/ubuntu eoan/main amd64 Packages
     release v=19.10,o=Ubuntu,a=eoan,n=eoan,l=Ubuntu,c=main,b=i386
     origin gb.archive.ubuntu.com
```

All `bionic` package repositories should be listed like the following example:

```
990 http://gb.archive.ubuntu.com/ubuntu bionic/main amd64 Packages
     release v=18.04,o=Ubuntu,a=bionic,n=bionic,l=Ubuntu,c=main,b=amd64
     origin gb.archive.ubuntu.com
```

Recommended to use `aptitude` to upgrade packages due to better conflict resolution ability. Using `apt` is also possible. 

Install `aptitude` with::

    $ sudo apt install aptitude

Test package installation and examine changes::

    $ sudo aptitude -s install python3-pyqt5.qwt python3-pyqt5.qtsvg -t eoan

Install packages::

    $ sudo aptitude -s install python3-pyqt5.qwt python3-pyqt5.qtsvg -t eoan

Example output from package installation:

```
The following NEW packages will be installed:
  libdouble-conversion3{a} libicu63{a} libncursesw6{a} libpcre2-16-0{a} libpython3.7{a} libpython3.7-minimal{a}
  libpython3.7-stdlib{a} libqt5core5a{a} libqt5dbus5{a} libqt5designer5{a} libqt5gui5{a} libqt5help5{a} libqt5network5{a}
  libqt5opengl5{a} libqt5printsupport5{a} libqt5sql5{a} libqt5sql5-sqlite{a} libqt5svg5{a} libqt5test5{a}
  libqt5widgets5{a} libqt5xml5{a} libqwt-qt5-6{a} libreadline8{a} libtinfo6{a} libxcb-xinerama0{a} libxcb-xinput0{a}
  python3-pyqt5{a} python3-pyqt5.qtsvg python3-pyqt5.qwt python3-sip{a} python3.7{a} python3.7-minimal{a}
  qt5-gtk-platformtheme{a} qttranslations5-l10n{a}
The following packages will be upgraded:
  libc-bin libc6 libidn2-0 libpython3-stdlib locales python3 python3-minimal
7 packages upgraded, 34 newly installed, 0 to remove and 1297 not upgraded.
Need to get 38.7 MB of archives. After unpacking 140 MB will be used.
The following packages have unmet dependencies:
 python3-dev : Depends: python3 (= 3.6.7-1~18.04) but 3.7.5-1 is to be installed
 python3-zope.interface : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 libc6-dbg : Depends: libc6 (= 2.27-3ubuntu1) but 2.30-0ubuntu2.1 is to be installed
 libc6-dev : Depends: libc6 (= 2.27-3ubuntu1) but 2.30-0ubuntu2.1 is to be installed
 python3-systemd : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-protobuf : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-reportlab-accel : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-gi-cairo : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-brlapi : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-pil : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-netifaces : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-cups : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-renderpm : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-simplejson : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 hplip : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-cffi-backend : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-yaml : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-dbus : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-cairo : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 libc-dev-bin : Depends: libc6 (< 2.28) but 2.30-0ubuntu2.1 is to be installed
 python3-gi : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-crypto : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-nacl : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
 python3-apt : Depends: python3 (< 3.7) but 3.7.5-1 is to be installed
The following actions will resolve these dependencies:

      Remove the following packages:
1)      hplip [3.17.10+repack0-5 (bionic, now)]

      Install the following packages:
2)      gcc-9-base [9.2.1-9ubuntu2 (eoan)]
3)      libapt-pkg5.90 [1.9.4ubuntu0.1 (eoan-security, eoan-updates)]
4)      libimagequant0 [2.12.2-1.1 (eoan)]
5)      libprotobuf17 [3.6.1.3-2 (eoan)]
6)      libpython3.7-dev [3.7.5-2~19.10ubuntu1 (eoan-security, eoan-updates)]
7)      python3.7-dev [3.7.5-2~19.10ubuntu1 (eoan-security, eoan-updates)]
8)      zlib1g-dev [1:1.2.11.dfsg-1ubuntu3 (eoan)]

      Upgrade the following packages:
9)      apt [1.6.12ubuntu0.1 (bionic-security, bionic-updates, now) -> 1.9.4ubuntu0.1 (eoan-security, eoan-updates)]
10)     apt-utils [1.6.12ubuntu0.1 (bionic-security, bionic-updates, now) -> 1.9.4ubuntu0.1 (eoan-security, eoan-updates)]
11)     libc-dev-bin [2.27-3ubuntu1 (bionic, now) -> 2.30-0ubuntu2.1 (eoan-updates)]
12)     libc6-dbg [2.27-3ubuntu1 (bionic, now) -> 2.30-0ubuntu2.1 (eoan-updates)]
13)     libc6-dev [2.27-3ubuntu1 (bionic, now) -> 2.30-0ubuntu2.1 (eoan-updates)]
14)     libfreetype6 [2.8.1-2ubuntu2 (bionic, now) -> 2.9.1-4 (eoan)]
15)     libgnutls30 [3.5.18-1ubuntu1.3 (bionic-security, bionic-updates, now) -> 3.6.9-5ubuntu1.2 (eoan-security, eoan-updates)
16)     libhogweed4 [3.4-1 (bionic, now) -> 3.4.1-1 (eoan)]
17)     libnettle6 [3.4-1 (bionic, now) -> 3.4.1-1 (eoan)]
18)     libp11-kit0 [0.23.9-2 (bionic, now) -> 0.23.17-2 (eoan)]
19)     libpython3-dev [3.6.7-1~18.04 (bionic-updates, now) -> 3.7.5-1 (eoan)]
20)     libstdc++6 [8.4.0-1ubuntu1~18.04 (bionic-security, bionic-updates, now) -> 9.2.1-9ubuntu2 (eoan)]
21)     libtasn1-6 [4.13-2 (bionic, now) -> 4.14-3 (eoan)]
22)     p11-kit-modules [0.23.9-2 (bionic, now) -> 0.23.17-2 (eoan)]
23)     printer-driver-postscript-hp [3.17.10+repack0-5 (bionic, now) -> 3.19.6+dfsg0-1ubuntu1 (eoan)]
24)     python3-apt [1.6.5ubuntu0.3 (bionic-updates, now) -> 1.9.0ubuntu1.4 (eoan-updates)]
25)     python3-brlapi [5.5-4ubuntu2.0.1 (bionic-updates, now) -> 5.6-11ubuntu2 (eoan)]
26)     python3-cairo [1.16.2-1 (bionic, now) -> 1.16.2-1build2 (eoan)]
27)     python3-cffi-backend [1.11.5-1 (bionic, now) -> 1.12.3-1build1 (eoan)]
28)     python3-crypto [2.6.1-8ubuntu2 (bionic, now) -> 2.6.1-10 (eoan)]
29)     python3-cups [1.9.73-2 (bionic, now) -> 1.9.73-2build2 (eoan)]
30)     python3-dbus [1.2.6-1 (bionic, now) -> 1.2.12-1 (eoan)]
31)     python3-dev [3.6.7-1~18.04 (bionic-updates, now) -> 3.7.5-1 (eoan)]
32)     python3-distutils [3.6.9-1~18.04 (bionic-updates, now) -> 3.7.5-1build1 (eoan-updates)]
33)     python3-gi [3.26.1-2ubuntu1 (bionic-updates, now) -> 3.34.0-1 (eoan)]
34)     python3-gi-cairo [3.26.1-2ubuntu1 (bionic-updates, now) -> 3.34.0-1 (eoan)]
35)     python3-nacl [1.1.2-1build1 (bionic, now) -> 1.3.0-2 (eoan)]
36)     python3-netifaces [0.10.4-0.1build4 (bionic, now) -> 0.10.4-1build3 (eoan)]
37)     python3-pil [5.1.0-1ubuntu0.2 (bionic-security, bionic-updates, now) -> 6.1.0-1ubuntu0.2 (eoan-security, eoan-updates)]
38)     python3-protobuf [3.0.0-9.1ubuntu1 (bionic, now) -> 3.6.1.3-2 (eoan)]
39)     python3-renderpm [3.4.0-3ubuntu0.1 (bionic-security, bionic-updates, now) -> 3.5.23-1ubuntu0.1 (eoan-security, eoan-upd
40)     python3-reportlab-accel [3.4.0-3ubuntu0.1 (bionic-security, bionic-updates, now) -> 3.5.23-1ubuntu0.1 (eoan-security, e
41)     python3-simplejson [3.13.2-1 (bionic, now) -> 3.16.0-1ubuntu1 (eoan)]
42)     python3-systemd [234-1build1 (bionic, now) -> 234-3 (eoan)]
43)     python3-yaml [3.12-1build2 (bionic, now) -> 5.1.2-1 (eoan)]
44)     python3-zope.interface [4.3.2-1build2 (bionic, now) -> 4.3.2-1build4 (eoan)]
45)     zlib1g [1:1.2.11.dfsg-0ubuntu2 (bionic, now) -> 1:1.2.11.dfsg-1ubuntu3 (eoan)]

      Leave the following dependencies unresolved:
46)     libsane-hpaio recommends hplip (= 3.17.10+repack0-5)
47)     ubuntu-desktop recommends hplip



Accept this solution? [Y/n/q/?]
```

Then build the source::

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
