# -*- coding: utf-8 -*-

from Timba.TDL import *
from Timba.utils import curry
import traceback
import Meow
import Meow.OptionTools
import Meow.Context
import math
from math import *

# find out where Tigger lives -- either it's in the path, or we add it
try:
  import Tigger
except:
  sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))));
  import Tigger

from Tigger.Models import ModelHTML,ModelClasses

class TiggerSkyModel (object):
  """Interface to a Tigger-format sky model."""
  def __init__ (self,filename=None,include_options=False,option_namespace='tiggerlsm'):
    """Initializes a TiggerSkyModel object.
    A filename and a format may be specified, although the actual file will\
    only be loaded on demand.
    If include_options=True, immediately instantiates the options. If False, it is up to
    the caller to include the options in his menus.
    """;
    self.tdloption_namespace = option_namespace;
    self._compile_opts = [];
    self._runtime_opts = [];
    self.filename = filename;
    self.lsm = None;
    # immediately include options, if needed
    if include_options:
      TDLCompileOptions(*self.compile_options());
      TDLRuntimeOptions(*self.runtime_options());

  def compile_options (self):
    """Returns list of compile-time options""";
    if not self._compile_opts:
      self._compile_opts = [
        TDLOption("filename","Tigger LSM file",
                   TDLFileSelect("*."+ModelHTML.DefaultExtension,default=self.filename,exist=True),
                   namespace=self),
        TDLOption('lsm_subset',"Source subset",["all"],more=str,namespace=self,
                  doc="""<P>You can enter source names separated by space. "all" selects all sources. "=<i>tagname</i>"
                  selects all sources with a given tag. "-<i>name</i>" deselects the named sources. "-=<i>tagname</i>" deselects sources by tag,</P>"""),
        TDLMenu("Make solvable source parameters",
          TDLOption('lsm_solvable_tag',"Solvable source tag",[None,"solvable"],more=str,namespace=self,
                    doc="""If you specify a tagname, only sources bearing that tag will be made solvable. Use 'None' to make all sources solvable."""),
          TDLOption("solve_I","I",False,namespace=self),
          TDLOption("solve_Q","Q",False,namespace=self),
          TDLOption("solve_U","U",False,namespace=self),
          TDLOption("solve_V","V",False,namespace=self),
          TDLOption("solve_spi","spectral index",False,namespace=self),
          TDLOption("solve_pos","position",False,namespace=self),
          TDLOption("solve_RM","rotation measure",False,namespace=self),
          TDLOption("solve_shape","shape (for extended sources)",False,namespace=self),
          toggle='solvable_sources',namespace=self,
        )
    ];
    return self._compile_opts;

  def runtime_options (self):
    """Makes and returns list of compile-time options""";
    # no runtime options, for now
    return self._runtime_opts;

  def source_list (self,ns,max_sources=None,**kw):
    """Reads LSM and returns a list of Meow objects.
    ns is node scope in which they will be created.
    Keyword arguments may be used to indicate which of the source attributes are to be
    created as Parms, use e.g. I=Meow.Parm(tags="flux") for this.
    The use_parms option may override this.
    """;
    if self.filename is None:
      return [];
    # load the sky model
    if self.lsm is None:
      self.lsm = ModelHTML.loadModel(self.filename);

    # sort by brightness
    sources = sorted(self.lsm.sources,lambda a,b:cmp(b.brightness(),a.brightness()));

    # extract subset, if specified
    if self.lsm_subset != "all":
      all = set([src.name for src in sources]);
      srcs = set();
      for ispec,spec in enumerate(self.lsm_subset.split()):
        spec = spec.strip();
        if spec:
          # if first spec is a negation, then implictly select all sources first
          if not ispec and spec[0] == "-":
            srcs = all;
          if spec == "all":
            srcs = all;
          elif spec.startswith("="):
            srcs.update([ src.name for src in sources if getattr(src,spec[1:],False) ]);
          elif spec.startswith("-="):
            srcs.difference_update([ src.name for src in sources if getattr(src,spec[2:],False) ]);
          elif spec.startswith("-"):
            srcs.discard(spec[1:]);
          else:
            srcs.add(spec);

      # make list
      sources = [ src for src in sources if src.name in srcs ];

    parm = Meow.Parm(tags="source solvable");
    # make copy of kw dict to be used for sources not in solvable set
    kw_nonsolve = dict(kw);
    # and update kw dict to be used for sources in solvable set
    if self.solvable_sources:
      if self.solve_I:
        kw.setdefault("I",parm);
      if self.solve_Q:
        kw.setdefault("Q",parm);
      if self.solve_U:
        kw.setdefault("U",parm);
      if self.solve_V:
        kw.setdefault("V",parm);
      if self.solve_spi:
        kw.setdefault("spi",parm);
      if self.solve_RM:
        kw.setdefault("RM",parm);
      if self.solve_pos:
        kw.setdefault("ra",parm);
        kw.setdefault("dec",parm);
      if self.solve_shape:
        kw.setdefault("sx",parm);
        kw.setdefault("sy",parm);
        kw.setdefault("phi",parm);

    # make Meow list
    source_model = []

  ## Note: conversion from AIPS++ componentlist Gaussians to Gaussian Nodes
  ### eX, eY : multiply by 2
  ### eP: change sign
    for src in sources:
      # get source pos/flux parameters
      attrs = dict(ra=src.pos.ra,dec=src.pos.dec,I=src.flux.I,
        Q=getattr(src.flux,'Q',None),
        U=getattr(src.flux,'U',None),
        V=getattr(src.flux,'V',None),
        RM=getattr(src.flux,'rm',None),
        freq0=getattr(src.flux,'freq0',None) or (src.spectrum and getattr(src.spectrum,'freq0',None)),
        spi=src.spectrum and getattr(src.spectrum,'spi',None));
      if isinstance(src.shape,ModelClasses.Gaussian):
        symmetric = src.shape.ex == src.shape.ey;
        attrs['sx'] = src.shape.ex*2;
        attrs['sy'] = src.shape.ey*2;
        attrs['phi'] = -src.shape.pa;
      ## construct parms or constants for source attributes
      ## if source is solvable (solvable_source_set of None means all are solvable),
      ## use the kw dict, else use the nonsolve dict for source parameters
      if self.lsm_solvable_tag is None or getattr(src,self.lsm_solvable_tag,False):
        solvable = True;
        kwdict = kw;
      else:
        solvable = False;
        kwdict = kw_nonsolve;
      for key,value in list(attrs.iteritems()):
        meowparm = kwdict.get(key);
        if isinstance(meowparm,Meow.Parm):
          attrs[key] = meowparm.new(value);
        elif meowparm is not None:
          attrs[key] = value;
      # construct a direction
      direction = Meow.Direction(ns,src.name,attrs['ra'],attrs['dec'],static=not self.solve_pos);

      # construct a point source or gaussian or FITS image, depending on source shape class
      if src.shape is None:
        msrc = Meow.PointSource(ns,name=src.name,
                I=attrs['I'],Q=attrs['Q'],U=attrs['U'],V=attrs['V'],
                direction=direction,
                spi=attrs['spi'],freq0=attrs['freq0'],RM=attrs['RM']);
      elif isinstance(src.shape,ModelClasses.Gaussian):
        if symmetric:
          size,phi = attrs['sx'],None;
        else:
          size,phi = [attrs['sx'],attrs['sy']],attrs['phi'];
        msrc = Meow.GaussianSource(ns,name=src.name,
                I=attrs['I'],Q=attrs['Q'],U=attrs['U'],V=attrs['V'],
                direction=direction,
                spi=attrs['spi'],freq0=attrs['freq0'],
                size=size,phi=phi);
      elif isinstance(src.shape,ModelClasses.FITSImage):
        msrc = Meow.FITSImageComponent(ns,name=src.name,
                    filename=src.shape.filename,
                    direction=direction);
        msrc.set_options(fft_pad_factor=(src.shape.pad or 2));

      msrc.solvable = solvable;

      # copy all extra attrs
      for attr,val in src.getExtraAttributes():
        msrc.set_attr(attr,val);

      # makie sure Iapp exists (init with I if it doesn't)
      if msrc.get_attr('Iapp',None) is None:
        msrc.set_attr('Iapp',src.flux.I);

      source_model.append(msrc);

#    print [ x.name for x in source_model[:10] ];
    return source_model;

