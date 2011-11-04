# -*- coding: utf-8 -*-
"""Defines various useful functions and constants for parsing FITS headers""";


# Table of Stokes parameters corresponding to Stokes axis indices
# Taken from Table 7, Greisen, E. W., and Calabretta, M. R., Astronomy & Astrophysics, 395, 1061-1075, 2002
# (http://www.aanda.org/index.php?option=article&access=bibcode&bibcode=2002A%2526A...395.1061GFUL)
# So StokesNames[1] == "I", StokesNames[-1] == "RR", StokesNames[-8] == "YX", etc.
StokesNames = [ "","I","Q","U","V","YX","XY","YY","XX","LR","RL","LL","RR"  ];
# complex axis convention
ComplexNames = [ "","real","imag","weight" ];



def isAxisTypeX (ctype):
  """Checks if given CTYPE corresponds to the X axis""";
  return any([ ctype.startswith(prefix) for prefix in "RA","GLON","ELON","HLON","SLON" ]) or \
          ctype in ("L","X","LL","U","UU");


def isAxisTypeY (ctype):
  """Checks if given CTYPE corresponds to the Y axis""";
  return any([ ctype.startswith(prefix) for prefix in "DEC","GLAT","ELAT","HLAT","SLAT" ]) or \
          ctype in ("M","Y","MM","V","VV");
