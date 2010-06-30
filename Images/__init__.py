
import os.path

FITS_ExtensionList = [ ".fts",".FTS",".fits",".FITS" ];

def isFITS (filename):
    return os.path.splitext(filename)[1] in FITS_ExtensionList;
