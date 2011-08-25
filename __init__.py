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

# version numbers
try:
  import version_info.release
  release_string = 'version %s'%version_info.release.release;
except:
  release_string = 'using svn version';
try:
  import version_info.svn_revision
  svn_revision_string = "(svn revision %s)"%version_info.svn_revision.svn_revision;
  svn_revision_html = "<p align='right'>(svn revision %s)</p>"%version_info.svn_revision.svn_revision;
except:
  svn_revision_string = '';
  svn_revision_html = '';

# These functions are used for startup timings, and initialized properly by the main "tigger" script.
# If imported as a module from elsewhere, provide dummy versions
if 'TiggerMain' not in sys.modules:
  startup_dprint = startup_dprintf = lambda *dum:None;
# else init as standalone app
else:
  # init debug printing
  import Kittens.utils
  _verbosity = Kittens.utils.verbosity(name="tigger");
  dprint = _verbosity.dprint;
  dprintf = _verbosity.dprintf;

  import Kittens.pixmaps
  pixmaps = Kittens.pixmaps.PixmapCache("tigger");

  import Kittens.config
  ConfigFile = Kittens.config.DualConfigParser("tigger.conf");
  Config = Kittens.config.SectionParser(ConfigFile,"Tigger");

  from Kittens.widgets import BusyIndicator

from Tigger.Models.Formats import load,save,listFormats
