Version = "0.1";

import sys

if 'Timba.TDL' in sys.modules:
  # These functions are used for startup timings, and initialized properly by the main "tigger" script.
  # If running in TDL mode, provide dummy versions
  startup_dprint = startup_dprintf = lambda *dum:None;

# else normal standalone mode
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
