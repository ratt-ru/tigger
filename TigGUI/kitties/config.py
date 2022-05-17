#!/usr/bin/env python3

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

import os
import sys
from configparser import ConfigParser, NoSectionError, NoOptionError, DuplicateSectionError

import os.path

_default_system_paths = [
    "/usr/local/Timba",
    "/usr/Timba/",
    "/etc/"]

_default_user_path = os.path.expanduser("~/")


class DualConfigParser:
    """A dual config parser taking into account both system-wide files
    and user defaults. Any changes are stored in the user defaults."""

    def __init__(self, filename="timba.conf",
                 system_paths=_default_system_paths,
                 user_path=_default_user_path):
        self.syscp = ConfigParser()
        system_paths = [os.path.join(path, filename) for path in system_paths]
        self.syscp.read(system_paths)
        self.usercp = ConfigParser()
        self._user_file = os.path.join(user_path, "." + filename)
        self.usercp.read([self._user_file])

    def add_section(self, _section):
        if not self.syscp.has_section(_section):
            self.syscp.add_section(_section)
        if not self.usercp.has_section(_section):
            self.usercp.add_section(_section)

    def has_section(self, _section):
        return self.syscp.has_section(_section) or self.usercp.has_section(_section)

    def _get(self, _method, _section, _option, default=None, init=False, save=False):
        _section = _section or self.defsection  # TODO - defsection is unresolved for DualConfigParser
        # try user defaults
        try:
            return getattr(self.usercp, _method)(_section, _option)
        except (NoSectionError, NoOptionError, ValueError):
            error = sys.exc_info()[1]
        # try systemwide
        try:
            return getattr(self.syscp, _method)(_section, _option)
        except (NoSectionError, NoOptionError, ValueError):
            if default is not None and _option is not None:
                self.syscp.set(_section, _option, str(default))
                if init or save:
                    self.usercp.set(_section, _option, str(default))
                    if save:
                        self.usercp.write(open(self._user_file, "w"))
                return default
            # no default, so re-raise the error
            raise error

    def set(self, _section, _option, _value, save=True):
        _value = str(_value)
        # try to get option first, and do nothing if no change
        try:
            if self.get(_section, _option) == _value:
                return
        except (NoSectionError, NoOptionError):
            pass
        # save to user section
        try:
            self.usercp.add_section(_section)
        except DuplicateSectionError:
            pass
        self.usercp.set(_section, _option, _value)
        if save:
            with open(self._user_file, "w") as f:
                self.usercp.write(f)

    def has_option(self, _section, _option):
        return self.syscp.has_option(_section, _option) or \
               self.usercp.has_option(_section, _option)

    def get(self, _section, _option, default=None):
        return self._get('get', _option, default, _section)


class SectionParser:
    """A section parser is basically a ConfigParser with a default section name."""

    def __init__(self, _parser, _section):
        """Creates a SectionParser from a DualConfigParser and a section name"""
        self.parser = _parser
        _parser.add_section(_section)
        self.section = _section

    def has_option(self, _option, section=None):
        return self.parser.has_option(section or self.section, _option)

    def get(self, _option, default=None, section=None, init=False, save=False):
        return self.parser._get('get', section or self.section, _option, default, init=init, save=save)

    def getint(self, _option, default=None, section=None, init=False, save=False):
        return self.parser._get('getint', section or self.section, _option, default, init=init, save=save)

    def getfloat(self, _option, default=None, section=None, init=False, save=False):
        return self.parser._get('getfloat', section or self.section, _option, default, init=init, save=save)

    def getbool(self, _option, default=None, section=None, init=False, save=False):
        return self.parser._get('getboolean', section or self.section, _option, default, init=init, save=save)

    def set(self, _option, _value, section=None, save=True):
        return self.parser.set(section or self.section, _option, _value, save=save)


Config = DualConfigParser()
_section_parsers = {}


def section(name):
    global _section_parsers
    return _section_parsers.setdefault(name, SectionParser(Config, name))


if __name__ == '__main__':
    conf = Config('test')
    print('test1:', conf.get('test1', 1))
    print('test2:', conf.getint('test2', 2))
    print('test3:', conf.getfloat('test3', 3.0))
    try:
        print('test4:', conf.get('test4'))
    except:
        print('test4:', sys.exc_info())
    try:
        print('test5:', conf.get('test5'))
    except:
        print('test5:', sys.exc_info())
    conf.set('test6', 'abc')
    conf.set('test7', 1)
    conf.set('test8', 1.0)
    conf.set('test9', True)
    print('has test1:', conf.has_option('test1'))
    print('has test4:', conf.has_option('test4'))
