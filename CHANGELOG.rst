================
Tigger Changelog
================
1.6.1.1
Minor bug fixes to window and docking config loading upon Tigger startup

1.6.2
=====

* Version bump in preparation for release
* Adds selected profile feature (ALT+LeftButton)
* WCS projection is now optimised for multiple images
* WCS projection provides 2 modes, switchable via the new WCS Projection menu
* Adds FITS header and WCS projection viewer
* Coordinate measurements have been fixed
* Fixes plot layout handling
* Fixes dockable widget sizing and placement
* Fixes historgram mouse wheel movement
* Fixes issue #139 - Live and selected profiles
* Fixes issue #140 - WCS projection
* Fixes issue #141 - flake8 errors
* Various other minor refactorings and adjustments

1.6.1.2 
=======

* Updated the dependency version of tigger-lsm to 1.7.2

1.6.1.1
=====

* Minor bug fixes to window and docking config loading upon Tigger startup

1.6.1
=====

* Version bump in preparation for release
* Supports Ubuntu 22.04
* Beta support for Ubuntu 22.04 ARM64
* Added FITS header preview pane to file dialog
* Dependent on the latest tigger-lsm (1.7.1)
* Fixed float errors with updated library API's
* Fixed dockable widgets and window sizing
* Refactored plot zooming
* Re-enabled splash screen
* Fixes venv pip3 bug
* Fixes issue #131
* Install script 'setup.py install' has been replaced by pip
* Updated URL's
* GitHub Actions are now compatible with 'act'
* Actions now test VENV installations on Ubuntu 20.04 and 22.04
* Improved Action tests and logging

1.6.0
=====

* Version bump in preparation for release
* Dependent on latest PyQt-Qwt from GitHub
* Updates to tigger-lsm API calls
* Fixes bug with window size and dockable widgets
* Added Ubuntu LTS installation script for 18.04, 20.04 and 21.04
* Added Tigger application launcher with icon
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


