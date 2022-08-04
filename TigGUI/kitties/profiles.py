# Copyright (C) 2002-2022
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

import json
import numpy as np

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
        self.__verifyArrs(xdata, ydata)
        self._xdata = xdata.copy()
        self._ydata = ydata.copy()

    def __verifyArrs(self, xdata, ydata):
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
            "x_data": self._xdata.tolist(),
            "y_data": self._ydata.tolist()
        }
        with open(filename, "w+") as fprof:
            json.dump(prof, fprof, indent=4)

        dprint(0, f"Saved current selected profile as {filename}")


class MutableTiggerProfile(TiggerProfile):
    """
        Mutable Tigger profile
        profilename: A name for this profile
        axisname: Name for the axis
        axisunit: Unit for the axis (as taken from FITS CUNIT)
        xdata: profile x axis data (1D ndarray of shape of ydata)
        ydata: profile y axis data (1D ndarray)
    """
    def __init__(self, profilename, axisname, axisunit, xdata, ydata):
        TiggerProfile.__init__(self, profilename, axisname, axisunit, xdata, ydata)

    def setAxesData(self, xdata, ydata):
        self.__verifyArrs(xdata, ydata)
        self._xdata = xdata.copy()
        self._ydata = ydata.copy()

    @property
    def profileName(self):
        return self._profilename

    @property
    def axisName(self):
        return self._axisname

    @property
    def axisUnit(self):
        return self._axisunit

    @profileName.setter
    def profileName(self, name):
        self._profilename = name

    @axisName.setter
    def axisName(self, name):
        self._axisname = name

    @axisUnit.setter
    def axisUnit(self, unit):
        self._axisunit = unit


class TiggerProfileFactory:
    def __init__(self, filename):
        raise NotImplementedError("Factory cannot be instantiated!")

    @classmethod
    def load(cls, filename):
        """ Loads a TigProf profile from file """
        with open(filename, "r") as fprof:
            try:
                fprof_content = fprof.read()
                prof = json.loads(fprof_content)
            except json.JSONDecodeError as e:
                raise IOError(
                    f"TigProf profile '{filename}' corrupted. Not valid json."
                ) from e

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
            except Exception as exc:
                raise IOError("Error parsing TigProf file version") from exc

            profname = prof["profile_name"]
            axisname = prof["axis"]
            axisunits = prof["units"]

            if (not isinstance(prof["x_data"], list) and not all(
                    map(lambda x: isinstance(x, float), prof["x_data"]))):
                raise IOError("Stored X data is not list of floats")
            xdata = np.array(prof["x_data"])

            if (not isinstance(prof["y_data"], list) and not all(
                    map(lambda x: isinstance(x, float), prof["y_data"]))):
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
