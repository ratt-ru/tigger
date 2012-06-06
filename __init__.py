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

matplotlib_nuked = False;

def nuke_matplotlib ():
  """Some people think nothing of importing matplotlib at every opportunity, with no regard
  to consequences. Tragically, some of these people also write Python code, and some of them
  are responsible for astLib. Seriously man, if I just want to pull in WCS support, why the fuck
  do I need the monstrous entirety of matplotlib to come along with it, especially since it
  kills things like Qt outright?
  This function prevents such perversitities from happening, by inserting dummy modules
  into the sys.modules dict. Call nuke_matplotlib() once, and all further attempts to
  import matplotlib by any other code will be cheerfully ignored.
  """;
  if 'pylab' not in sys.modules:
    # replace the modules referenced by astLib by dummy_module objects, which return a dummy callable for every attribute
    class dummy_module (object):
      def __getattr__ (self,name):
        return lambda *args,**kw:True;
    sys.modules['pylab'] = sys.modules['matplotlib'] = sys.modules['matplotlib.patches'] = dummy_module();
    matplotlib_nuked = True;

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
  import os.path
  ConfigFileName = ".tigger.conf";
  ConfigFile = Kittens.config.DualConfigParser("tigger.conf",["/usr/lib/Tigger",os.path.dirname(__file__)]);
  Config = Kittens.config.SectionParser(ConfigFile,"Tigger");

  from Kittens.widgets import BusyIndicator

from Tigger.Models.Formats import load,save,listFormats
