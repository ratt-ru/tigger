_registered_tools = [];

def getRegisteredTools ():
  return _registered_tools;

def registerTool (name,callback):
  _registered_tools.append((name,callback));

