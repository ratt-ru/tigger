# initializes GUI-related globals. Only called from the viewer

import os.path

import TigGUI.kitties.config
import TigGUI.kitties.pixmaps

pixmaps = TigGUI.kitties.pixmaps.PixmapCache("TigGUI")
ConfigFileName = ".tigger.conf"
ConfigFile = TigGUI.kitties.config.DualConfigParser("tigger.conf", ["/usr/lib/TigGUI", os.path.dirname(__file__)])
Config = TigGUI.kitties.config.SectionParser(ConfigFile, "Tigger")
