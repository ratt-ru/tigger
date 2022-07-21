from TigGUI.kitties.utils import verbosity
_verbosity = verbosity(name="profiles")
dprint = _verbosity.dprint
dprintf = _verbosity.dprintf

class TiggerProfile:
    def __init__(self, profilename, axisname, axisunit, xdata, ydata):
        self._profilename = profilename
        self._axisname = axisname
        self._axisunit = axisunit
        if xdata.size != ydata.size:
            raise ValueError("X-data must match Y-data size")
        if xdata.ndim != 1:
            raise ValueError("X-data must be 1D")
        if ydata.ndim != 1:
            raise ValueError("Y-data must be 1D")
        self._xdata = xdata
        self._ydata = ydata

    def saveProfile(self, filename):
        xdatastr = ",".join(map(str, self._xdata))
        ydatastr = ",".join(map(str,self._ydata))
        with open(filename, "w+") as fprof:
            fprof.write("# Tigger profile format\n")
            fprof.write(f"Version:\n{1.0}\n")
            fprof.write(f"Profile name:\n{self._profilename}\n")
            fprof.write(f"Axis:\n{self._axisname}\n")
            fprof.write(f"Units:\n{self._axisunit}\n")
            fprof.write(f"X-data:\n{xdatastr}\n")
            fprof.write(f"Y-data:\n{ydatastr}\n")
        dprint(0, f"Saved current selected profile as {filename}")