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

from Tigger.Models.Formats import load, save, listFormats
from Kittens.widgets import BusyIndicator
import Kittens.pixmaps
import Kittens.utils
import Kittens.config
import os.path


__version__ = "1.3.8"

release_string = __version__
svn_revision_string = __version__
svn_revision_html = __version__


matplotlib_nuked = False


startup_dprint = startup_dprintf = lambda *dum:None
_verbosity = Kittens.utils.verbosity(name="tigger")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf
pixmaps = Kittens.pixmaps.PixmapCache("Tigger")
ConfigFileName = ".tigger.conf"
ConfigFile = Kittens.config.DualConfigParser("tigger.conf",["/usr/lib/Tigger", os.path.dirname(__file__)])
Config = Kittens.config.SectionParser(ConfigFile,"Tigger")



def import_pyfits ():
  """Helper function to import pyfits and return it. Provides a workaround for
  pyfits-2.3, which is actually arrogant enough (fuck you with a bargepole, pyfits!) 
  to replace the standard warnings.formatwarning function with its own BROKEN version, 
  thus breaking all other code that uses the warnings module."""
  if 'pyfits' not in sys.modules:
    import pyfits
    import warnings
    if getattr(pyfits,'formatwarning',None) is warnings.formatwarning:
      def why_is_pyfits_overriding_warnings_formatwarning_with_a_broken_one_damn_you_pyfits (message,category,  filename,lineno,line=None):
        return str(message)+'\n'
      warnings.formatwarning = why_is_pyfits_overriding_warnings_formatwarning_with_a_broken_one_damn_you_pyfits
    if getattr(pyfits,'showwarning',None) is warnings.showwarning:
      def showwarning_damn_you_pyfits_damn_you_sincerely (message,category,filename,lineno,file=None,line=None):
        pyfits.showwarning(message,category,filename,lineno,file=file)
      warnings.showwarning = showwarning_damn_you_pyfits_damn_you_sincerely
  return pyfits


def nuke_matplotlib ():
  """Some people think nothing of importing matplotlib at every opportunity, with no regard
  to consequences. Tragically, some of these people also write Python code, and some of them
  are responsible for astLib. Seriously man, if I just want to pull in WCS support, why the fuck
  do I need the monstrous entirety of matplotlib to come along with it, especially since it
  kills things like Qt outright?
  This function prevents such perversitities from happening, by inserting dummy modules
  into the sys.modules dict. Call nuke_matplotlib() once, and all further attempts to
  import matplotlib by any other code will be cheerfully ignored.
  """
  if 'pylab' not in sys.modules:
    # replace the modules referenced by astLib by dummy_module objects, which return a dummy callable for every attribute
    class dummy_module (object):
      def __getattr__ (self,name):
        return 'nowhere' if name == '__file__' else (lambda *args,**kw:True)
    sys.modules['pylab'] = sys.modules['matplotlib'] = sys.modules['matplotlib.patches'] = dummy_module()
    matplotlib_nuked = True





