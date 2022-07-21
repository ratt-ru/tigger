import numpy as np
import json

from TigGUI.kitties.utils import verbosity
_verbosity = verbosity(name="profiles")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf

class TiggerProfile:
    __VER_MAJ__ = 1
    __VER_MIN__ = 0
    def __init__(self, profilename, axisname, axisunit, xdata, ydata):
        """ 
            Immutable Tigger profile 
            profilename: A name for this profile
            axisname: Name for the axis
            axisunit: Unit for the axis (as taken from FITS CUNIT)
            xdata: profile x axis data (1D ndarray of shape of ydata)
            ydata: profile y axis data (1D ndarray)
        """
        # update if you update this format
        self._version_maj = TiggerProfile.__VER_MAJ__
        self._version_min = TiggerProfile.__VER_MIN__

        self._profilename = profilename
        self._axisname = axisname
        self._axisunit = axisunit
        if not isinstance(xdata, np.ndarray):
            raise ValueError("X-data must be ndarray type")
        if not isinstance(ydata, np.ndarray):
            raise ValueError("Y-data must be ndarray type")
        if xdata.size != ydata.size:
            raise ValueError("X-data must match Y-data size")
        if xdata.ndim != 1:
            raise ValueError("X-data must be 1D")
        if ydata.ndim != 1:
            raise ValueError("Y-data must be 1D")
        self._xdata = xdata.copy()
        self._ydata = ydata.copy()

    @property
    def xdata(self):
        return self._xdata.copy()
    
    @property
    def ydata(self):
        return self._ydata.copy()

    @property
    def profileName(self):
        return self._profilename

    @property
    def axisName(self):
        return self._axisname

    @property
    def axisUnit(self):
        return self._axisunit

    @property
    def version(self):
        return f"{self._version_maj}.{self._version_min}"

    def saveProfile(self, filename):
        prof = {
            "version": self.version,
            "profile_name": self._profilename,
            "axis": self._axisname,
            "units": self._axisunit,
            "x_data": list(self._xdata),
            "y_data": list(self._ydata)
        }
        with open(filename, "w+") as fprof:            
            fprof.write(json.dumps(prof))
            
        dprint(0, f"Saved current selected profile as {filename}")

class TiggerProfileFactory:
    def __init__(self, filename):
        raise NotImplemented("Factory cannot be instantiated!")
    
    @classmethod
    def load(cls, filename):
        """ Loads a TigProf profile from file """
        with open(filename, "r") as fprof:
            try:
                prof = json.load(fprof)
            except json.JSONDecodeError as e:
                raise IOError(f"TigProf profile '{filename}' corrupted. Not valid json.")
            __mandatory = set(["version", "profile_name", "axis",
                               "units", "x_data", "y_data"])
            for c in __mandatory:
                if c not in prof:
                    print(f"Profile file '{filename}' is missing field '{c}'")
            
            try:
                vmaj, vmin = prof.get("version", "").split(".")
                vstr = f"{vmaj}.{vmin}"
                supvstr = f"{TiggerProfile.__VER_MAJ__}.{TiggerProfile.__VER_MIN__}"
                if float(vstr) > float(supvstr):
                    msg = f"Loaded TigProf profile version {vstr} is newer " \
                          f"than supported profile version {supvstr}. " \
                          f"Attempting to convert to version {supvstr}."
                    dprint(0, msg)
            except:
                raise IOError("Error parsing TigProf file version")
            
            profname = prof["profile_name"]
            axisname = prof["axis"]
            axisunits = prof["units"]

            if not isinstance(prof["x_data"], list) and \
                not all(map(lambda x: isinstance(x, float), prof["x_data"])):
                raise IOError("Stored X data is not list of floats")
            xdata = np.array(prof["x_data"])
            
            if not isinstance(prof["y_data"], list) and \
                not all(map(lambda x: isinstance(x, float), prof["y_data"])):
                raise IOError("Stored Y data is not list of floats")
            ydata = np.array(prof["y_data"])

            if xdata.ndim != 1:
                raise IOError("Stored X data is not 1D")

            if ydata.ndim != 1:
                raise IOError("Stored Y data is not 1D")

            if xdata.size != ydata.size:
                raise IOError("Stored X data not the same shape as Y data")
            
            # Success
            tigprof = TiggerProfile(profname, axisname, axisunits, xdata, ydata)
            dprint(0, f"Loaded profile from {filename}")
            return tigprof