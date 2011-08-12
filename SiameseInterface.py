# -*- coding: utf-8 -*-

#
#% $Id$ 
#
#
# Copyright (C) 2002-2011
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

from Timba.TDL import *
from Timba.utils import curry
import traceback
import Meow
import Meow.OptionTools
import Meow.Context
import Meow.ParmGroup
import math
from math import *
import os.path

# find out where Tigger lives -- either it's in the path, or we add it
try:
  import Tigger
except:
  sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))));
  import Tigger

from Tigger.Models import ModelHTML,ModelClasses

# this dict determines how source attributes are grouped into "parameter subgroups"
_Subgroups = dict(I="I",Q="Q",U="U",V="V",
    ra="pos",dec="pos",RM="RM",spi="spi",
    sx="shape",sy="shape",phi="shape");
_SubgroupOrder = "I","Q","U","V","pos","spi","RM","shape";

class TiggerSkyModel (object):
  """Interface to a Tigger-format sky model."""
  def __init__ (self,filename=None,include_options=False,tdloption_namespace='tiggerlsm'):
    """Initializes a TiggerSkyModel object.
    A filename and a format may be specified, although the actual file will\
    only be loaded on demand.
    If include_options=True, immediately instantiates the options. If False, it is up to
    the caller to include the options in his menus.
    """;
    self.tdloption_namespace = tdloption_namespace;
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
          TDLOption('lsm_solve_group_tag',"Group independent solutions by tag",[None,"cluster"],more=str,namespace=self,
                    doc="""If you specify a tagname, sources will be grouped by the value of the tag,
                    and each group will be treated as an independent solution."""),
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
    # this will be a dict of lists of solvable subgroups
    parms = [];
    subgroups = {};
    if self.solvable_sources:
      subgroup_order = [];
      for sgname in _SubgroupOrder:
        if getattr(self,'solve_%s'%sgname):
          sg = subgroups[sgname] = [];
          subgroup_order.append(sgname);

    # make Meow list
    source_model = []

    for src in sources:
      if self.solvable_sources:
        # independent groups?
        if self.lsm_solve_group_tag:
          independent_sg = sgname = "%s:%s"%(self.lsm_solve_group_tag,getattr(src,self.lsm_solve_group_tag,"unknown"));
        else:
          independent_sg = "";
          sgname = 'source:%s'%src.name;
        if sgname in subgroups:
          sgsource = subgroups[sgname];
        else:
          sgsource = subgroups[sgname] = [];
          subgroup_order.append(sgname);
      # make dict of source parametrs: for each parameter we have a value,subgroup pair
      attrs = dict(
        ra=     src.pos.ra,
        dec=    src.pos.dec,
        I=      src.flux.I,
        Q=      getattr(src.flux,'Q',None),
        U=      getattr(src.flux,'U',None),
        V=      getattr(src.flux,'V',None),
        RM=     getattr(src.flux,'rm',None),
        freq0=  getattr(src.flux,'freq0',None) or (src.spectrum and getattr(src.spectrum,'freq0',None)),
        spi=    src.spectrum and getattr(src.spectrum,'spi',None)
      );
      if isinstance(src.shape,ModelClasses.Gaussian):
        symmetric = src.shape.ex == src.shape.ey;
        attrs['sx']  = src.shape.ex*2;
        attrs['sy']  = src.shape.ey*2;
        attrs['phi'] = -src.shape.pa;
      # construct parms or constants for source attributes, depending on whether the source is solvable or not
      # If source is solvable and this particular attribute is solvable, replace
      # value in attrs dict with a Meq.Parm.
      solvable = False;
      if self.solvable_sources and (not self.lsm_solvable_tag  or getattr(src,self.lsm_solvable_tag,False)):
        for parmname,value in attrs.items():
          sgname = _Subgroups.get(parmname,None);
          if sgname in subgroups:
            solvable = True;
            parm = attrs[parmname] = ns[src.name](parmname) << Meq.Parm(value or 0,
                                                                tags=["solvable",sgname],solve_group=independent_sg);
            subgroups[sgname].append(parm);
            sgsource.append(parm);
            parms.append(parm);

      # construct a direction
      direction = Meow.Direction(ns,src.name,attrs['ra'],attrs['dec'],static=not solvable or not self.solve_pos);

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
        if solvable and 'shape' in subgroups:
          subgroups['pos'] += direction.get_solvables();
      elif isinstance(src.shape,ModelClasses.FITSImage):
        msrc = Meow.FITSImageComponent(ns,name=src.name,
                    filename=src.shape.filename,
                    direction=direction);
        msrc.set_options(fft_pad_factor=(src.shape.pad or 2));

      msrc.solvable = solvable;

      # copy all extra attrs
      for attr,val in src.getExtraAttributes():
        msrc.set_attr(attr,val);

      # make sure Iapp exists (init with I if it doesn't)
      if msrc.get_attr('Iapp',None) is None:
        msrc.set_attr('Iapp',src.flux.I);

      source_model.append(msrc);

    # if any solvable parms were made, make a parmgroup and solve job for them
    if parms:
      if os.path.isdir(self.filename):
        table_name = os.path.join(self.filename,"sources.fmep");
      else:
        table_name = os.path.splitext(self.filename)[0]+".fmep";
      # make list of Subgroup objects for every non-empty subgroup
      sgs = [];
      for sgname in subgroup_order:
        sglist = subgroups.get(sgname,None);
        if sglist:
          sgs.append(Meow.ParmGroup.Subgroup(sgname,sglist));
      # make main parm group
      pg_src = Meow.ParmGroup.ParmGroup("source parameters",parms,
                  subgroups=sgs,
                  table_name=table_name,table_in_ms=False,bookmark=True);
      # now make a solvejobs for the source
      Meow.ParmGroup.SolveJob("cal_source","Solve for source parameters",pg_src);


    return source_model;

