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
import string
import sys
import traceback
import weakref

import os.path
import re
import time
import types

_time0 = time.time()


class recdict(dict):
    """A recdict is basically a dict whose contents may also be
    accessed via attributes, using the rec.field notation.
    """

    def __getattr__(self, name):
        if name.startswith('__'):
            return dict.__getattr__(self, name)
        # else try to access attribute anyway, to see if we have one
        try:
            return dict.__getattr__(self, name)
        except AttributeError:
            pass
        return dict.__getitem__(self, name)

    # __setattr__: sets entry in dict
    def __setattr__(self, name, value):
        if name.startswith('__'):
            return dict.__setattr__(self, name, value)
        return dict.__setitem__(self, name, value)

    # __delattr__: deletes key
    def __delattr__(self, name):
        if name.startswith('__'):
            return dict.__delattr__(self, name)
        return dict.__delitem__(self, name)


def collapseuser(path):
    """If path begins with the home directory, replaces the start of the path with "~/". Essentially the reverse of os.path.expanduser()"""
    home = os.path.join(os.path.expanduser("~"), "")
    if path.startswith(home):
        path = os.path.join("~", path[len(home):])
    return path


def type_maker(objtype, **kwargs):
    def maker(x):
        if isinstance(x, objtype):
            return x
        return objtype(x)

    return maker


def extract_stack(f=None, limit=None):
    """equivalent to traceback.extract_stack(), but also works with psyco
    """
    if f is not None:
        raise RuntimeError("Timba.utils.extract_stack: f has to be None, don't ask why")
    # normally we can just use the traceback.extract_stack() function and
    # cut out the last frame (which is just ourselves). However, under psyco
    # this seems to return an empty list, so we use sys._getframe() instead
    lim = limit
    if lim is not None:
        lim += 1
    tb = traceback.extract_stack(None, lim)
    if tb:
        return tb[:-1]  # skip current frame
    # else presumably running under psyco
    return nonportable_extract_stack(f, limit)


def nonportable_extract_stack(f=None, limit=None):
    if f is not None:
        raise RuntimeError("Timba.utils.nonportable_extract_stack: f has to be None, don't ask why")
    tb = []
    fr = sys._getframe(1)  # caller's frame
    while fr and (limit is None or len(tb) < limit):
        tb.insert(0, (fr.f_code.co_filename, fr.f_lineno, fr.f_code.co_name, None))
        fr = fr.f_back
    return tb


_proc_status = '/proc/%d/status' % os.getpid()

_scale = {'kB': 1024.0, 'mB': 1024.0 * 1024.0,
          'KB': 1024.0, 'MB': 1024.0 * 1024.0}


def _VmB(VmKey):
    """Private.
    """
    global _proc_status, _scale
    # get pseudo file  /proc/<pid>/status
    try:
        t = open(_proc_status)
        v = t.read()
        t.close()
    except:
        return 0.0  # non-Linux?
    # get VmKey line e.g. 'VmRSS:  9999  kB\n ...'
    i = v.index(VmKey)
    v = v[i:].split(None, 3)  # whitespace
    if len(v) < 3:
        return 0.0  # invalid format?
    # convert Vm value to bytes
    return float(v[1]) * _scale[v[2]]


def _memory(since=0.0):
    """Return memory usage in bytes.
    """
    return _VmB('VmSize:') - since


def _resident(since=0.0):
    """Return resident memory usage in bytes.
    """
    return _VmB('VmRSS:') - since


def _stacksize(since=0.0):
    """Return stack size in bytes.
    """
    return _VmB('VmStk:') - since


#
# === class verbosity ===
# Verbosity includes methods for verbosity levels and conditional printing
#
class verbosity:
    _verbosities = {}
    _levels = {}
    _parse_argv = True

    _timestamps = False
    _timestamps_modulo = 0

    _memstamps = True

    @staticmethod
    def enable_timestamps(enable=True, modulo=60):
        verbosity._timestamps = enable
        verbosity._timestamps_modulo = modulo

    @staticmethod
    def enable_memstamps(enable=True, modulo=60):
        verbosity._memstamps = enable

    @staticmethod
    def timestamp():
        if verbosity._timestamps:
            hdr = "%5.2f " % ((time.time() - _time0) % verbosity._timestamps_modulo)
        else:
            hdr = ""
        if verbosity._memstamps:
            mem = _memory()
            hdr += "%.1fGb " % (float(mem) / (1024 ** 3))
        return hdr

    @staticmethod
    def set_verbosity_level(context, level):
        verbosity._levels[context] = level
        vv = verbosity._verbosities.get(context, None)
        if vv:
            vv.set_verbose(level)

    @staticmethod
    def disable_argv():
        verbosity._parse_argv = False

    def __init__(self, verbose=0, stream=None, name=None, tb=2):
        if not __debug__:
            verbose = 0
        (self.verbose, self.stream, self._tb) = (verbose, stream, tb)
        # setup name
        if name:
            self.verbosity_name = name
        else:
            if self.__class__ is verbosity:
                raise RuntimeError("""When creating a verbosity object directly,
          a name must be specified.""")
            self.verbosity_name = name = self.__class__.__name__
        # look for argv to override debug levels (unless they were already set via set_verbosity_level above)
        if verbosity._levels:
            self.verbose = verbosity._levels.get(name, 0)
            print("Registered verbosity context: " + name + " = " + self.verbose)
        elif verbosity._parse_argv:
            # NB: sys.argv doesn't always exist -- e.g., when embedding Python
            # it doesn't seem to be present.  Hence the check.
            argv = getattr(sys, 'argv', None)
            have_debug = False
            if argv:
                patt = re.compile('-d' + name + '=(.*)$')
                for arg in argv[1:]:
                    if arg.startswith('-d'):
                        have_debug = True
                    try:
                        self.verbose = int(patt.match(arg).group(1))
                    except:
                        pass
            if have_debug:
                print("Registered verbosity context:" + name + "=" + str(self.verbose))
        # add name to map
        self._verbosities[name] = self

    def __del__(self):
        if self.verbosity_name in self._verbosities:
            del self._verbosities[self.verbosity_name]

    def dheader(self, tblevel=-2):
        if self._tb:
            tb = extract_stack()
            try:
                (filename, line, funcname, text) = tb[tblevel]
            except:
                return "%s%s (no traceback): " % (self.timestamp(), self.get_verbosity_name())
            filename = filename.split('/')[-1]
            if self._tb > 1:
                return "%s%s(%s:%d:%s): " % (self.timestamp(), self.get_verbosity_name(), filename, line, funcname)
            else:
                return "%s%s(%s): " % (self.timestamp(), self.get_verbosity_name(), funcname)
        else:
            return "%s%s: " % (self.timestamp(), self.get_verbosity_name())

    def dprint(self, level, *args):
        if level <= self.verbose:
            stream = self.stream or sys.stderr
            stream.write(self.dheader(-3))
            stream.write(string.join(list(map(str, args)), ' ') + '\n')

    def dprintf(self, _level, _format, *args):
        if _level <= self.verbose:
            stream = self.stream or sys.stderr
            try:
                s = _format % args
            except:
                stream.write('dprintf format exception: ' + str(_format) + '\n')
            else:
                stream.write(self.dheader(-3))
                stream.write(s)

    def get_verbose(self):
        return self.verbose

    def set_verbose(self, verbose):
        self.verbose = verbose

    def set_stream(self, stream):
        self.stream = stream

    def set_verbosity_name(self, name):
        self.verbosity_name = name

    def get_verbosity_name(self):
        return self.verbosity_name


def _print_curry_exception():
    (et, ev, etb) = sys.exc_info()
    print("%s: %s" % (getattr(ev, '_classname', ev.__class__.__name__), getattr(ev, '__doc__', '')))
    if hasattr(ev, 'args'):
        print("  " + ' '.join(map(str, ev.args)))
    print('======== exception traceback follows:')
    traceback.print_tb(etb)


# curry() composes callbacks and such
# See The Python Cookbook recipe 15.7
def curry(func, *args, **kwds):
    def callit(*args1, **kwds1):
        kw = kwds.copy()
        kw.update(kwds1)
        a = args + args1
        # print(f"curry args {args}")
        # print(f"curry args1 {args1}")
        # print(f"curry args a {a}")
        # print(f"curry kw {kw}")
        try:
            return func(*a, **kw)
        except Exception as e:
            print("======== curry: exception while calling a curried function")
            print(f"  function:{func}")
            print(f"  args: {a}")
            print(f"  kwargs: {kw}")
            print(f"  exception: {e}")
            _print_curry_exception()
            raise

    return callit


# Extended curry() version
# The _argslice argument is applied to the *args of the
# curry when it is subsequently called; this allows only a subset of the
# *args to be passed to the curried function.
def xcurry(func, _args=(), _argslice=slice(0), _kwds={}, **kwds):
    kwds0 = _kwds.copy()
    kwds0.update(kwds)
    if not isinstance(_args, tuple):
        _args = (_args,)

    def callit(*args1, **kwds1):
        a = _args + args1[_argslice]
        kw = kwds0.copy()
        kw.update(kwds1)
        try:
            return func(*a, **kw)
        except:
            print("======== xcurry: exception while calling a curried function")
            print("  function:" + func)
            print("  args:" + a)
            print("  kwargs:" + kw)
            _print_curry_exception()
            raise

    return callit


class PersistentCurrier:
    """This class provides curry() and xcurry() instance methods that
    internally store the curries in a list. This is handy for currying
    callbacks to be passed to, e.g., PyQt slots: since PyQt holds the callbacks
    via weakrefs, using the normal curry() method to compose a callback
    on-the-fly would cause it to disappear immediately.
    """

    def _add_curry(self, cr):
        try:
            self._curries.append(cr)
        except AttributeError:
            self._curries = [cr]
        return cr

    def curry(self, func, *args, **kwds):
        # curry debug output
        # print(f"curry: func {func} args {args} kwds {kwds}")
        return self._add_curry(curry(func, *args, **kwds))

    def xcurry(self, func, *args, **kwds):
        return self._add_curry(xcurry(func, *args, **kwds))

    def clear(self):
        self._curries = []


class WeakInstanceMethod:
    # return value indicating call of a weakinstancemethod whose object
    # has gone
    DeadRef = object()

    def __init__(self, method):
        if type(method) != types.MethodType:
            raise TypeError("weakinstancemethod must be constructed from an instancemethod")
        (self.__func__, self.__self__) = (method.__func__, weakref.ref(method.__self__))

    def __bool__(self):
        return self.__self__() is not None

    def __call__(self, *args, **kwargs):
        obj = self.__self__()
        if obj is None:
            return self.DeadRef
        return self.__func__(obj, *args, **kwargs)


def weakref_proxy(obj):
    """returns either a weakref.proxy for the object, or if object is already a proxy,
    returns itself."""
    if type(obj) in weakref.ProxyTypes:
        return obj
    else:
        return weakref.proxy(obj)
