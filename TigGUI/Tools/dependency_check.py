# -*- coding: utf-8 -*-
#
# % $Id$
#
#
# Copyright (C) 2002-2021
# The MeqTree Foundation &
# ASTRON (Netherlands Foundation for Research in Astronomy)
# P.O.Box 2, 7990 AA Dwingeloo, The Netherlands
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>,
# or write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""Checks that Tigger-LSM, PyQt5 and Qwt are available for Tigger to operate."""
try:
    from Tigger.Models import ModelClasses  # check tigger-lsm is available

    from PyQt5.Qt import Qt  # check PyQt5 is available

    from PyQt5.QtOpenGL import QGLWidget  # check PyQt5 Qt OpenGL is available

    from PyQt5.QtSvg import QSvgWidget  # check PyQt5 Qt SVG is available

    from PyQt5.Qwt import QwtPlotZoomer  # check Qwt is available

    test_qwt = callable(getattr(QwtPlotZoomer, 'setZoomStack', None))  # check correct version of Qwt is installed

except ImportError:
    deps_available = False
    pass
else:
    if test_qwt:
        deps_available = True
    else:
        deps_available = False

if not deps_available:
    import sys

    error_msg = "Error: Dependencies have not been met, please check your installation. " \
                "See https://github.com/ska-sa/tigger for further information."
    sys.exit(error_msg)
