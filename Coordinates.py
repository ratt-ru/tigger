from Tigger import startup_dprint
startup_dprint(1,"start of Coordinates");

import math
from numpy import sin,cos,arcsin,arccos;
startup_dprint(1,"imported numpy");
import pyfits
startup_dprint(1,"imported pyfits");

DEG = math.pi/180;

startup_dprint(1,"importing WCS");

# WCS pulls astLib which pulls in pylab and matplotlib.patches, talk about spaghetti dependencies, duh! Override these by dummies,
# if not already imported
import sys
if 'pylab' not in sys.modules:
  # replace the modules referenced by astLib by dummy_module objects, which return a dummy callable for every attribute
  class dummy_module (object):
    def __getattr__ (self,name):
      return lambda *args,**kw:True;
  sys.modules['pylab'] = sys.modules['matplotlib'] = sys.modules['matplotlib.patches'] = dummy_module();

try:
  from astLib.astWCS import WCS
except ImportError:
  print "Failed to import the astLib.astWCS module. Please install the astLib package (http://astlib.sourceforge.net/)."

startup_dprint(1,"imported WCS");

class _Projector (object):
    """This is an abstract base class for all projection classes below. A projection class can be used to create projector objects for
    conversion between world (ra,dec) and projected (l,m) coordinates.

    * A projector is instantiated as proj = Proj(ra0,dec0)      # ra0,dec0 is projection centre
    * converts ra,dec->l,m as
          l,m = proj.lm(ra,dec)
    * converts l,m->ra,dec as
          ra,dec = proj.radec(l,m)
    * converts angular offsets (from 0,0 point) into l,m:
          l,m = proj.offset(dra,ddec);

    Alternativelty, there are class methods which do not require one to instantiate a projector object:

    * Proj.radec_lm(ra,dec,ra0,dec0)
    * Proj.lm_radec(l,m,ra0,dec0)
    * Proj.offset_lm(dra,ddec,ra0,dec0)
    """
    def __init__ (self,ra0,dec0):
      self.ra0,self.dec0,self.sin_dec0,self.cos_dec0 = ra0,dec0,sin(dec0),cos(dec0);

    def __eq__ (self,other):
      """By default, two projections are the same if their classes match, and their ra0/dec0 match."""
      return type(self) is type(other) and self.ra0 == other.ra0 and self.dec0 == other.dec0;

    @classmethod
    def radec_lm (cls,ra,dec,ra0,dec0):
      return cls(ra0,dec0).lm(ra,dec);

    @classmethod
    def lm_radec (cls,l,m,ra0,dec0):
      return cls(ra0,dec0).radec(l,m);

    @classmethod
    def offset_lm (cls,dra,ddec,ra0,dec0):
      return cls(ra0,dec0).offset(dra,ddec);

    def lm (self,ra,dec):
      raise TypeError,"lm() not yet implemented in projection %s"%type(self).__name__;

    def offset (self,dra,ddec):
      raise TypeError,"offset() not yet implemented in projection %s"%type(self).__name__;

    def radec (self,l,m):
      raise TypeError,"radec() not yet implemented in projection %s"%type(self).__name__;

class Projection (object):
  """Projection is a container for the different projection classes.
  Each Projection class can be used to create a projection object: proj = Proj(ra0,dec0), with lm(ra,dec) and radec(l,m) methods.
  """;

  class FITSWCSpix (_Projector):
    """FITS WCS projection, as determined by a FITS header. lm is in pixels (0-based)."""
    def __init__ (self,header):
      """Constructor. Create from filename (treated as FITS file), or a FITS header object""";
      # attach to FITS file or header
      if isinstance(header,str):
        header = pyfits.open(header)[0].header;
      else:
        self.wcs = WCS(header,mode="pyfits");
      ra0,dec0 = self.wcs.getCentreWCSCoords();
      self.xpix0,self.ypix0 = self.wcs.wcs2pix(*self.wcs.getCentreWCSCoords());
      self.xscale = self.wcs.getXPixelSizeDeg()*DEG;
      self.yscale = self.wcs.getYPixelSizeDeg()*DEG;
      _Projector.__init__(self,ra0*DEG,dec0*DEG);

    def lm (self,ra,dec):
      return self.wcs.wcs2pix(ra/DEG,dec/DEG)

    def radec (self,l,m):
      ra,dec = self.wcs.pix2wcs(l,m);
      return ra*DEG,dec*DEG;

    def offset (self,dra,ddec):
      return self.xpix0 - dra/self.xscale,self.ypix0 + ddec/self.xscale;

  class FITSWCS (FITSWCSpix):
    """FITS WCS projection, as determined by a FITS header. lm is renormalized to radians, l is reversed, 0,0 is at reference pixel."""
    def __init__ (self,header):
      """Constructor. Create from filename (treated as FITS file), or a FITS header object""";
      Projection.FITSWCSpix.__init__(self,header);

    def lm (self,ra,dec):
      l,m = self.wcs.wcs2pix(ra/DEG,dec/DEG);
      l = (self.xpix0-l)*self.xscale;
      m = (m-self.ypix0)*self.yscale;
      return l,m;

    def radec (self,l,m):
      ra,dec = self.wcs.pix2wcs(self.xpix0-l/self.xscale,self.ypix0+m/self.yscale);
      return ra*DEG,dec*DEG;

    def offset (self,dra,ddec):
      return dra,ddec;

  @staticmethod
  def SinWCS (ra0,dec0):
    hdu = pyfits.PrimaryHDU();
    hdu.header.update('NAXIS',2);
    hdu.header.update('NAXIS1',3);
    hdu.header.update('NAXIS2',3);
    hdu.header.update('CTYPE1','RA---SIN');
    hdu.header.update('CDELT1',-1./60);
    hdu.header.update('CRPIX1',2);
    hdu.header.update('CRVAL1',ra0/DEG);
    hdu.header.update('CUNIT1','deg     ');
    hdu.header.update('CTYPE2','DEC--SIN');
    hdu.header.update('CDELT2',1./60);
    hdu.header.update('CRPIX2',2);
    hdu.header.update('CRVAL2',dec0/DEG);
    hdu.header.update('CUNIT2','deg     ');
    return Projection.FITSWCS(hdu.header);
