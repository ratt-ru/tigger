================
Tigger Changelog
================

1.6.0
=====

* Version bump in preparation for release
* Dependent on latest PyQt-Qwt from GitHub
* Updates to tigger-lsm API calls
* Fixes bug with window size and dockable widgets
* Added Ubuntu 20.04 installation script
* Various bug fixes
* Various code tidying

1.5.0 beta
==========

* Ported from PyQt4 and Qwt 5, to PyQt 5 and Qwt 6
* Now depends on Tigger-LSM v1.7.0
* Dependent on OS installed PyQt 5 and Qwt 6 related packages
* Supports Ubuntu 20.04 LTS
* Support for High DPI displays and scaling
* Anti-aliasing rendering
* New dark mode theme
* New customisable GUI interface
* Custom QDockWidget (with Qt bug workaround)
* Dockable, tabbed and floating windows
* Exported PNG's now calculate maximum image resolution based on free memory resources
* New option to limit exported PNG images to 4K resolution
* Various bug fixes

1.3.9
=====

Changes since 1.3.8:
 
* Improve freq0 parsing logic (#84)
* Install vext.pyqt4 if in virtualenv (#86)
* Use KERN-2 in Dockerfile
* Define f0 outside the "if" block #87

1.3.8
=====

changes since 1.3.7:
 * hack around problem with pkg_resources package bug


1.3.5
=====

 * Provide MS list to tigger-convert --app-to-int operation (#69)
 * Tigger incompatible with pyfits>=3.4 (#71)
 * It's given the correct name (install_requires) so that it will actually have an
   effect on the package manager.
 * PyQt4 is removed from install_requires, since it is not a PyPA-installable package.
   Instead, a check is added to fail setup if it is not already installed.
 * Added missing scipy and pyfits dependencies.

1.3.3
=====

 * renamed package to astro-tigger to resolve name conflict on pypi


