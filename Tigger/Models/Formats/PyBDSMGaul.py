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

import sys,re

import Kittens.utils

from Tigger.Models import ModelClasses
from Tigger.Models import SkyModel
from Tigger import Coordinates
import Tigger.Models.Formats
from Tigger.Models.Formats import dprint,dprintf,ASCII

"""Loads a PyBDSM-format .gaul file. Gaul files are essentially ASCII tables with a very specific naming convention."""

# Gaus_id Isl_id Source_id Wave_id RA E_RA DEC E_DEC Total_flux
# E_Total_flux Peak_flux E_Peak_flux Xposn E_Xposn Yposn E_Yposn Maj E_Maj Min
# E_Min PA E_PA DC_Maj E_DC_Maj DC_Min E_DC_Min DC_PA E_DC_PA Isl_Total_flux
# E_Isl_Total_flux Isl_rms Isl_mean Resid_Isl_rms Resid_Isl_mean S_Code

format_mapping = dict(
  Gaus_id="name",
  RA="ra_d",E_RA="ra_err_d",DEC="dec_d",E_DEC="dec_err_d",
  Total_flux="i",E_Total_flux="i_err",
  Total_Q="q",E_Total_Q="q_err",
  Total_U="u",E_Total_U="u_err",
  Total_V="v",E_Total_V="v_err",
  DC_Maj="emaj_d",DC_Min="emin_d",DC_PA="pa_d",
  E_DC_Maj="emaj_err_d",E_DC_Min="emin_err_d",E_DC_PA="pa_err_d",
  SpI="spi",Spec_Indx="spi",E_Spec_Indx="spi_err",
  S_Code=":str:_pybdsm_S_Code"
);


def load (filename, freq0=None,**kw):
  """Imports a gaul table
  The 'freq0' argument supplies a default reference frequency (if one is not contained in the file.)
  If 'center_on_brightest' is True, the mpodel field center will be set to the brightest source.
  'min_extent' is minimal source extent (in radians), above which a source will be treated as a Gaussian rather than a point component.
  """
  srclist = [];
  id = None
  dprint(1,"importing PyBDSM gaul/srl file",filename);
  format = {};
  extension = filename.split(".")[-1]
  if extension == "srl":
    format_mapping['Source_id'] = format_mapping.pop('Gaus_id')
    id = "Source_id"
  # look for format string and reference freq, and build up format dict
  for line in file(filename):
    m = re.match("# Reference frequency .*?([0-9.eE+-]+)\s*Hz",line);
    if m:
      freq0 = kw['freq0'] = freq0 or float(m.group(1));
      dprint(2,"found reference frequency %g"%freq0);
    elif re.match("#(\s*[\w:]+\s+)+",line) and line.find(id if id else "Gaus_id") > 0:
      dprint(2,"found format string",line);
      fields = dict([ (name,i) for i,name in enumerate(line[1:].split()) ]); 
      # map known fields to their ASCII equivalents, the rest copy as custom float attributes with
      # a "pybdsm_" prefix
      for i,name in enumerate(line[1:].split()):
        if name in format_mapping:
          dprint(2,"Field",format_mapping[name],name,"is column",i)
          format[format_mapping[name]] = i;
        else:
          format[":float:_pybdsm_%s"%name] = i;
    if format and freq0:
      break;
  if not format:
    raise ValueError,"this .gaul file does not appear to contain a format string"
  # call ASCII.load() function now that we have the format dict
  kw['format'] = format;
  return ASCII.load(filename,**kw)

Tigger.Models.Formats.registerFormat("Gaul",load,"PyBDSM .gaul/.srl file",(".gaul",".srl",));
