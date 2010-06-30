import Import
import ModelHTML

model = Import.importASCII_DMS('lsm1.txt');
ModelHTML.saveModel('lsm.html',model);

model1 = ModelHTML.loadModel('lsm.html');
ModelHTML.saveModel('lsm1.html',model);

model2 = Import.importNEWSTAR('BAND0_BEAMED.MDL');
ModelHTML.saveModel('lsm2.html',model2);

