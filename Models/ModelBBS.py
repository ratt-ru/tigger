import Kittens.utils

_verbosity = Kittens.utils.verbosity(name="lsmbbs");
dprint = _verbosity.dprint;
dprintf = _verbosity.dprintf;

"""
The BBS sky model catalog file (*.cat, or *.catalog) is a human-readable text
file that contains a list of sources. The file should be in the `makesourcedb'
format. For details, please refer to
http://www.lofar.org/operations/doku.php?id=engineering:software:tools:makesourcedb#format_string
or
http://www.lofar.org/operations/doku.php?id=engineering:software:tools:bbs#creating_a_catalog_file
"""
    
def loadModel (filename):
    """
    Load a BBS sky model.
    """
    dprint(1, "loading model")
    raise RuntimeError, "ModelBBS.loadModel() is not yet implemented"


def saveModel (filename,model):
    """
    Save a BBS sky model.
    """
    dprint(1, "saving model")
    raise RuntimeError, "ModelBBS.loadModel() is not yet implemented"
