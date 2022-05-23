# Copyright (C) 2002-2022
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

import TigGUI.kitties.utils

import pkg_resources
try:
    __version__ = pkg_resources.require("astro-tigger")[0].version
except pkg_resources.DistributionNotFound:
    __version__ = "dev"

release_string = __version__
svn_revision_string = __version__
svn_revision_html = __version__

startup_dprint = startup_dprintf = lambda *dum: None
_verbosity = TigGUI.kitties.utils.verbosity(name="tiggui")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf
