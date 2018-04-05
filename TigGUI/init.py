# initializes GUI-related globals. Only called from the viewer

import os.path

import Kittens.config
import Kittens.pixmaps

pixmaps = Kittens.pixmaps.PixmapCache("TigGUI")
ConfigFileName = ".tigger.conf"
ConfigFile = Kittens.config.DualConfigParser("tigger.conf",["/usr/lib/TigGUI", os.path.dirname(__file__)])
Config = Kittens.config.SectionParser(ConfigFile,"Tigger")