# -*- coding: utf-8 -*-
#
#% $Id$
#
#
# Copyright (C) 2002-2011
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

import sys

import Kittens.config
import os.path
import Tigger
from Tigger import import_pyfits, nuke_matplotlib


__version__ = "1.4.0"

release_string = __version__
svn_revision_string = __version__
svn_revision_html = __version__

# initializes GUI-related globals. Only called from the viewer
def init_gui():
    from Kittens.widgets import BusyIndicator
    import Kittens.pixmaps
    import Kittens.utils
    global pixmaps, Config, ConfigFile, ConfigFileName
    pixmaps = Kittens.pixmaps.PixmapCache("TigGUI")
    ConfigFileName = ".tigger.conf"
    ConfigFile = Kittens.config.DualConfigParser("tigger.conf",["/usr/lib/TigGUI", os.path.dirname(__file__)])
    Config = Kittens.config.SectionParser(ConfigFile,"Tigger")


startup_dprint = startup_dprintf = lambda *dum:None
_verbosity = Kittens.utils.verbosity(name="tiggui")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf


