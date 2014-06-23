import aipy as ap
import numpy as np
import commands, os, time, math, ephem
import calibration_omni as omni
import optparse, sys
FILENAME = "omnical_PSA64.py"

##########################Sub-class#############################
class RedundantCalibrator_PAPER(omni.RedundantCalibrator):
	def __init__(self, aa):
		nTotalAnt = len(aa)
		omni.RedundantCalibrator.__init__(self, nTotalAnt)
		self.aa = aa

	def compute_redundantinfo(self, badAntenna = [], badUBL = [], antennaLocationTolerance = 1e-6):
		self.antennaLocationTolerance = antennaLocationTolerance
		self.badAntenna = badAntenna
		self.badUBL = badUBL
		self.antennaLocation = np.array([ant.pos for ant in self.aa])
		omni.RedundantCalibrator.compute_redundantinfo(self)
		
		



######################################################################
##############Config parameters###################################
######################################################################
o = optparse.OptionParser()
ap.scripting.add_standard_options(o, cal=True, pol=True)
opts,args = o.parse_args(sys.argv[1:])


ano = 'test'##This is the file name difference for final calibration parameter result file. Result will be saved in miriadextract_xx_ano.omnical
uvfiles = args
wantpols = {}
for p in opts.pol.split(','): wantpols[p] = ap.miraid.str2pol[p]
#wantpols = {'xx':ap.miriad.str2pol['xx']}#, 'yy':-6}#todo: 


aa = ap.cal.get_aa(opts.cal, np.array([.15]))
#infopaths = {'xx':'./redundantinfo_PSA32.txt', 'yy':'./redundantinfo_PSA32.txt'}
#arrayinfos = {'xx':'./arrayinfo_apprx_PAPER32.txt', 'yy':'./arrayinfo_apprx_PAPER32.txt'}
oppath = './results/'

removedegen = True
removeadditive = False

needrawcal = True #if true, (generally true for raw data) you need to take care of having raw calibration parameters in float32 binary format freq x nant
rawpaths = {'xx':"testrawphasecalparrad_xx", 'yy':"testrawphasecalparrad_yy"}



keep_binary_data = True
keep_binary_calpar = False


converge_percent = 0.01
max_iter = 10
step_size = .3

######################################################################
######################################################################
######################################################################

########Massage user parameters###################################
oppath += '/'


####get some info from the first uvfile   ################
uv=ap.miriad.UV(uvfiles[0])
nfreq = uv.nchan;
nant = uv['nants'] / 2 # 'nants' counting ant-pols, so divide 2
startfreq = uv['sfreq']
dfreq = uv['sdf']
del(uv)


####create redundant calibrators################
#calibrators = [omni.RedundantCalibrator(nant, info = infopaths[key]) for key in wantpols.keys()]
calibrators = [RedundantCalibrator_PAPER(aa) for key in wantpols.keys()]
for calibrator, key in zip(calibrators, wantpols.keys()):
	calibrator.compute_redundantinfo(badUBL = [0, 1, 2], antennaLocationTolerance = 1)
	calibrator.write_redundantinfo(infoPath = './redundantinfo_test_' + key + '.txt', overwrite = True)
###start reading miriads################
print FILENAME + " MSG:",  len(uvfiles), "uv files to be processed for " + ano
data, t, timing, lst = omni.importuvs(uvfiles, [calibrator.info for calibrator in calibrators], wantpols)
print FILENAME + " MSG:",  len(t), "slices read."

###raw calibration################
if needrawcal:
	for p, key in zip(range(len(wantpols)), wantpols.keys()):
		rawcalpar = np.fromfile(rawpaths[key], dtype="complex64").reshape(nfreq, nant)
		data[p] = omni.apply_calpar(data[p], rawcalpar, calibrators[p].totalVisibilityId)

###Save various files read################
#np.savetxt('miriadextract_' + ano + "_sunpos.dat", sunpos[:len(t)], fmt='%8.5f')
f = open(oppath + 'miriadextract_' + ano + "_localtime.dat",'w')
for time in timing:
	f.write("%s\n"%time)
f.close()
f = open(oppath + 'miriadextract_' + ano + "_lsthour.dat",'w')
for l in lst:
	f.write("%s\n"%l)
f.close()


####calibrate################
print FILENAME + " MSG: starting calibration."
for p, calibrator in zip(range(len(wantpols)), calibrators):
	calibrator.nTime = len(t)
	calibrator.nFrequency = nfreq
	calibrator.removeDegeneracy = removedegen
	calibrator.removeAdditive = removeadditive
	calibrator.keepData = keep_binary_data
	calibrator.keepCalpar = keep_binary_calpar
	calibrator.convergePercent = converge_percent
	calibrator.maxIteration = max_iter
	calibrator.stepSize = step_size
	print calibrator.nTime, calibrator.nFrequency
	calibrator.readyForCpp()
	calibrator.loglincal(data[p],verbose=True)

#########Test results############
correctresult = np.sum(np.fromfile("test.omnical", dtype = 'float32').reshape(14,203,165),axis=2).flatten()#summing the last dimension because when data contains some 0 and some -0, C++ code return various phasecalibration parameters on different systems, when all other numbers are nan. I do the summation to avoid it failing the euqality check when the input is trivially 0s.

newresult = np.sum(calibrators[-1].rawCalpar,axis=2).flatten()
if (len(newresult) == len(correctresult)) and ((newresult == correctresult) | (np.isnan(newresult) & np.isnan(correctresult))).all():
	print "TEST PASSED!"
elif (len(newresult) == len(correctresult)) and ([abs((j-i)/j) < 10**-6 for i,j in zip(newresult, correctresult)] | (np.isnan(newresult) & np.isnan(correctresult))).all():
	print "TEST PASSED! Note: There seem to be minor numerical differences on the level of 10^-6."
else:
	for i in range(len(newresult)):
		if abs((newresult[i]-correctresult[i])/correctresult[i]) >= 10**-6:
			print i, newresult[i], correctresult[i]
	print "TEST FAILED :("

os.remove(oppath + 'miriadextract_' + ano + "_localtime.dat")
os.remove(oppath + 'miriadextract_' + ano + "_lsthour.dat")
