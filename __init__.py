# -*- coding: utf-8 -*-
Version = "0.1.0";

import sys

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

# provide some convenience methods
def load (filename):
  """Loads and returns a native-format sky model."""
  import Models.ModelHTML
  return Models.ModelHTML.loadModel(filename);
