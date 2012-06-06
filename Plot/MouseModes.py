from Tigger import *
from PyQt4.Qt import *
import Kittens.utils
from Kittens.utils import curry,PersistentCurrier

_verbosity = Kittens.utils.verbosity(name="mmod");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;


_Contexts = dict(image=1,model=2);

WHEELUP = "WheelUp";
WHEELDOWN = "WheelDown";

MM_ZWIN = "zoom-window";
MM_ZUNDO = "zoom-undo";
MM_ZREDO = "zoom-redo";
MM_UNZOOM = "unzoom";
MM_MEAS = "measure";
MM_STATS = "stats";
MM_SELSRC = "select-source";
MM_SELWIN = "select-window";
MM_SELWINPLUS = "select-window-plus";
MM_DESEL = "deselect-window";

_AllFuncs = [ MM_ZWIN,MM_ZUNDO,MM_ZREDO,MM_UNZOOM,
             MM_MEAS,MM_STATS,MM_SELSRC,MM_SELWIN,MM_SELWINPLUS,MM_DESEL ];

FuncDoc = {
    MM_ZWIN: "Zoom into window (click-drag) or zoom in at point (double-click)",
    MM_ZUNDO: "Zoom out to previous view",
    MM_ZREDO: "Zoom in to previous view",
    MM_UNZOOM: "Zoom fully out",
    MM_MEAS: "Measuring ruler (click and drag)",
    MM_STATS: "Stats in box (click and drag)",
    MM_SELSRC: "Select nearest source",
    MM_SELWIN: "Select sources in window",
    MM_SELWINPLUS: "Extend selection with sources in window",
    MM_DESEL: "Deselect sources in window"
};

_DefaultModes = "Mouse3,Mouse2,Mouse1";
_DefaultInitialMode = "Mouse3";

class MouseModeManager (QObject):
  class MouseMode (object):
    def __init__ (self,mid):
      self.id = mid;
      self.name = self.icon = self.tooltip = None;
      self.contexts = [];
      self.submodes = [];
      self.patterns = {};
      self.qa = None;

    def addAction (self,menu,qag,callback,toolbar=None):
      self.qa = menu.addAction(self.name,callback);
      icon = self.icon and getattr(pixmaps,self.icon,None);
      icon and self.qa.setIcon(icon.icon());
      self.qa.setCheckable(True);
      qag.addAction(self.qa);
      toolbar and toolbar.addAction(self.qa);

  def __init__ (self,parent,menu,toolbar):
    QObject.__init__(self,parent);
    self._currier = PersistentCurrier();
    # get list of mouse modes from config
    modelist = [];
    for mid in Config.get("mouse-modes",_DefaultModes).split(","):
      if not ConfigFile.has_section(mid):
        print "ERROR: unknown mouse-mode '%s', skipping. Check your %s."%(mid,ConfigFileName);
      else:
        modelist.append(self._readModeConfig(mid));
    self._modes = dict([ (mode.id,mode) for mode in modelist ]);
    self._qag_mode = QActionGroup(self);
    self._qag_submode = QActionGroup(self);
    self._all_submodes = [];
    # make entries for main modes
    for mode in modelist:
      mode.addAction(menu,self._qag_mode,callback=self._currier.curry(self._setMode,mode.id));
      if mode.submodes:
        self._all_submodes += list(mode.submodes);
    # make entries for submodes
    self._qa_submode_sep = menu.addSeparator();
    self._modes.update([ (mode.id,mode) for mode in self._all_submodes ]);
    for mode in self._all_submodes:
      mode.addAction(menu,self._qag_submode,toolbar=toolbar,callback=self._currier.curry(self._setSubmode,mode.id));
    # other init
    self._current_context = None;
    self._available_submodes = [];
    # set initial mode
    initmode = Config.get("current-mouse-mode",_DefaultInitialMode);
    if initmode not in self._modes:
      initmode = modelist[0].id;
    self._modes[initmode].qa.setChecked(True);
    self._setMode(initmode,write_config=False);

  def currentMode (self):
    return self._current_submode or self._current_mode;

  def setContext (self,has_image,has_model):
    self._current_context = (has_image and _Contexts['image'])|(has_model and _Contexts['model']);
    self._ensureValidSubmodes();

  def _ensureValidSubmodes (self):
    current = None;
    self._valid_submodes = [];
    # accumulate list of valid submodes, and find the checked-on one
    for mode in self._available_submodes:
      if not mode.contexts or not self._current_context or self._current_context&mode.contexts:
        self._valid_submodes.append(mode);
        mode.qa.setVisible(True);
        if mode.qa.isChecked():
          current = mode.id;
      else:
        mode.qa.setVisible(False);
    if self._valid_submodes:
      self._setSubmode(current or self._valid_submodes[0].id);

  def _setMode (self,mid,write_config=True):
    """Called when the mouse mode changes""";
    if write_config:
      Config.set("current-mouse-mode",mid);
    self._current_mode = mode = self._modes[mid];
    # hide submodes if any
    for mm in self._all_submodes:
      mm.qa.setVisible(False);
    self._qa_submode_sep.setVisible(bool(mode.submodes));
    self._current_submode = None;
    self._available_submodes = mode.submodes;
    # make relevant submodes visible, and make sure one is enabled
    if mode.submodes:
      self._ensureValidSubmodes();
    else:
      self.emit(SIGNAL("setMouseMode"),mode);

  def _setSubmode (self,mid):
    """Called when the mouse submode changes""";
    self._current_submode = mode = self._modes[mid];
    mode.qa.setChecked(True);
    # hide submodes if any
    for mm in self._all_submodes:
      mm.qa.setShortcuts([]);
    # set F4 shortcut to next submode
    if len(self._valid_submodes) > 1:
      for i,mm in enumerate(self._valid_submodes):
        if mm is mode:
          self._valid_submodes[(i+1)%len(self._valid_submodes)].qa.setShortcut(Qt.Key_F4);
          break;
    self.emit(SIGNAL("setMouseMode"),mode);

  def _readModeConfig (self,section,main_tooltip=None):
    """Reads the given config section (and uses the supplied defaults dict)
    and returns a dict of mouse_patterns,key_patterns per each function."""
    # read basic stuff
    mode = self.MouseMode(section);
    config = Kittens.config.SectionParser(ConfigFile,section);
    mode.name = config.get("name",section);
    mode.icon = config.get("icon","") or None;
    mode.contexts = sum([ _Contexts.get(x,0) for x in config.get("contexts","").split(",") ]);
    submodes = config.get("submodes","") or None;
    # eiher a mode with submodes, or a main mode
    if submodes:
      mode.tooltip = "<P>Your current mouse scheme is \"%s\".</P>"%mode.name;
      for mid in submodes.split(","):
        if ConfigFile.has_section(mid):
          mode.submodes.append(self._readModeConfig(mid,main_tooltip=mode.tooltip));
        else:
          print "ERROR: unknown submode '%s' in mode config section '%s', skipping/ Check your %s."%(mid,section,ConfigFileName);
    else:
      if main_tooltip:
        mode.tooltip =  main_tooltip +"""<P>In this scheme, available mouse functions depend on the selected mode.
        The current mode is %s. Use F4 to cycle through other modes.</P>"""%mode.name;
      else:
        mode.tooltip = "<P>Your current mouse scheme is: \"%s\".</P>"%mode.name;
      mode.tooltip += """<P>The following mouse functions are available:</P><BR><TABLE>\n""";
      patterns = {};
      # get basic patterns
      for func in _AllFuncs:
        # get pattern
        pattern =   config.get(func,"");
        if not pattern:
          continue;
        mouse_pattern = key_pattern = None;
        for pat in pattern.split(";"):
          pat = pat.strip();
          if pat and pat.lower() != "none":
            # split by "+" and lookup each identifier in the Qt namespace
            scomps = pat.split("+");
            try:
              comps = [ x if x in (WHEELUP,WHEELDOWN) else getattr(Qt,x) for x in scomps ];
            except AttributeError:
              print "WARNING: can't parse '%s' for function '%s' in mode config section '%s', disabling. Check your %s."%(pat,func,section,ConfigFileName);
              continue;
            # append key/button code and sum of modifiers to the key or keyboard pattern list
            if scomps[-1].startswith("Key_"):
              if key_pattern:
                print "WARNING: more than one key pattern for function '%s' in mode config section '%s', ignoring. Check your %s."%(func,section,ConfigFileName);
              else:
                key_pattern = comps[-1],sum(comps[:-1]);
            else:
              if mouse_pattern:
                print "WARNING: more than one mouse pattern for function '%s' in mode config section '%s', ignoring. Check your %s."%(func,section,ConfigFileName);
              else:
                mouse_pattern = comps[-1],sum(comps[:-1]);
        mode.tooltip += "<TR><TD>%s:&nbsp;&nbsp;</TD><TD>%s</TD></TR>\n"%(pattern,FuncDoc[func]);
        mode.patterns[func] = (mouse_pattern or (0,0),key_pattern or (0,0));
      mode.tooltip += "</TABLE><BR>";
    return mode;
