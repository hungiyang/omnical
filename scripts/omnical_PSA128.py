#!/usr/bin/env python

import aipy as ap
import numpy as np
import commands, os, time, math, ephem
import omnical.calibration_omni as omni
import optparse, sys
import scipy.signal as ss
FILENAME = "omnical_PSA128.py"

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
		self.antennaLocation = np.zeros((self.nTotalAnt,3))
		for i in range(len(self.aa.ant_layout)):
			for j in range(len(self.aa.ant_layout[0])):
				self.antennaLocation[self.aa.ant_layout[i][j]] = np.array([i, j, 0])
		self.preciseAntennaLocation = np.array([ant.pos for ant in self.aa])
		omni.RedundantCalibrator.compute_redundantinfo(self)





######################################################################
##############Config parameters###################################
######################################################################
o = optparse.OptionParser()

ap.scripting.add_standard_options(o, cal=True, pol=True)
o.add_option('-t', '--tag', action = 'store', default = 'PSA128', help = 'tag name of this calibration')
o.add_option('-d', '--datatag', action = 'store', default = 'PSA128', help = 'tag name of this data set')
o.add_option('-i', '--infopath', action = 'store', default = '/data2/home/hz2ug/omnical/doc/redundantinfo_PSA128_17ba.bin', help = 'redundantinfo file to read')
o.add_option('--add', action = 'store_true', help = 'whether to enable crosstalk removal')
o.add_option('--nadd', action = 'store', type = 'int', default = -1, help = 'time steps w to remove additive term with. for running average its 2w + 1 sliding window.')
o.add_option('--datapath', action = 'store', default = None, help = 'uv file or binary file folder')
o.add_option('-o', '--outputpath', action = 'store', default = None, help = 'output folder')
o.add_option('-k', '--skip', action = 'store_true', help = 'whether to skip data importing from uv')

opts,args = o.parse_args(sys.argv[1:])
skip = opts.skip

ano = opts.tag##This is the file name difference for final calibration parameter result file. Result will be saved in miriadextract_xx_ano.omnical
dataano = opts.datatag#ano for existing data and lst.dat
sourcepath = opts.datapath
oppath = opts.outputpath
uvfiles = args
for uvf in uvfiles:
	if not os.path.isdir(uvf):
		uvfiles.remove(uvf)
if len(uvfiles) == 0:
	print "ERROR: No valid uv files detected in input. Exiting!"
	quit()

wantpols = {}
for p in opts.pol.split(','): wantpols[p] = ap.miriad.str2pol[p]
#wantpols = {'xx':ap.miriad.str2pol['xx']}#, 'yy':-6}#todo:


aa = ap.cal.get_aa(opts.cal, np.array([.15]))
infopathxx = opts.infopath
infopathyy = opts.infopath

#badAntenna = [37]
#badUBL = []



infopaths = {'xx': infopathxx, 'yy': infopathyy}


removedegen = True
if opts.add and opts.nadd > 0:
	removeadditive = True
	removeadditiveperiod = opts.nadd
else:
	removeadditive = False
	removeadditiveperiod = -1

needrawcal = False #if true, (generally true for raw data) you need to take care of having raw calibration parameters in float32 binary format freq x nant
#rawpaths = {'xx':"testrawphasecalparrad_xx", 'yy':"testrawphasecalparrad_yy"}



keep_binary_data = True
keep_binary_calpar = True


converge_percent = 0.001
max_iter = 20
step_size = .3

######################################################################
######################################################################
######################################################################

########Massage user parameters###################################
sourcepath += '/'
utcPath = sourcepath + 'miriadextract_' + dataano + "_localtime.dat"
lstPath = sourcepath + 'miriadextract_' + dataano + "_lsthour.dat"

####get some info from the first uvfile   ################
uv=ap.miriad.UV(uvfiles[0])
nfreq = uv.nchan;
nant = uv['nants']
#startfreq = uv['sfreq']
#dfreq = uv['sdf']
del(uv)




###start reading miriads################
if skip:
	with open(utcPath) as f:
		timing = f.readlines()
	data = [np.fromfile(sourcepath + 'data_' + dataano + '_' + key, dtype = 'complex64').reshape((len(timing), nfreq, len(aa) * (len(aa) + 1) / 2)) for key in wantpols.keys()]
else:
	print FILENAME + " MSG:",  len(uvfiles), "uv files to be processed for " + ano
	data, t, timing, lst = omni.importuvs(uvfiles, calibrators[0].totalVisibilityId, wantpols)#, nTotalAntenna = len(aa))
	print FILENAME + " MSG:",  len(t), "slices read."

	if keep_binary_data:
		f = open(utcPath,'w')
		for time in timing:
			f.write("%s\n"%time)
		f.close()
		f = open(lstPath,'w')
		for l in lst:
			f.write("%s\n"%l)
		f.close()
		for p,key in zip(range(len(wantpols)), wantpols.keys()):
			data[p].tofile(oppath + 'data_' + dataano + '_' + key, dtype = 'complex64')

####create redundant calibrators################
#calibrators = [omni.RedundantCalibrator(nant, info = infopaths[key]) for key in wantpols.keys()]
calibrators = {}
for p, key in zip(range(len(data)), wantpols.keys()):
	calibrators[key] = RedundantCalibrator_PAPER(aa)
	calibrators[key].read_redundantinfo(infopaths[key])
	calibrators[key].nTime = len(timing)
	calibrators[key].nFrequency = nfreq

	###prepare rawCalpar for each calibrator and consider, if needed, raw calibration################
	if needrawcal:
		raise Exception("Raw calpar not coded for the case where you need starting raw calibration!")
	else:
		calibrators[key].rawCalpar = np.zeros((calibrators[key].nTime, calibrators[key].nFrequency, 3 + 2 * (calibrators[key].Info.nAntenna + calibrators[key].Info.nUBL)),dtype='float32')


	####calibrate################
	calibrators[key].removeDegeneracy = removedegen
	calibrators[key].convergePercent = converge_percent
	calibrators[key].maxIteration = max_iter
	calibrators[key].stepSize = step_size

	################first round of calibration	#########################
	print FILENAME + " MSG: starting calibration on %s %s."%(dataano, key),
	print calibrators[key].nTime, calibrators[key].nFrequency
	additivein = np.zeros_like(data[p])
	calibrators[key].logcal(data[p], additivein, verbose=True)
	additivein[:,:,calibrators[key].Info.subsetbl] = calibrators[key].lincal(data[p], additivein, verbose=True)
	#######################remove additive###############################

	nadditiveloop = 1
	for i in range(nadditiveloop):
		weight = ss.convolve(np.ones(additivein.shape[0]), np.ones(removeadditiveperiod * 2 + 1), mode='same')
		for f in range(additivein.shape[1]):#doing for loop to save memory usage at the expense of negligible time
			additivein[:,f] = ss.convolve(additivein[:,f], np.ones(removeadditiveperiod * 2 + 1)[:, None], mode='same')/weight[:, None]
		calibrators[key].computeUBLFit = False
		additivein[:,:,calibrators[key].Info.subsetbl] = additivein[:,:,calibrators[key].Info.subsetbl] + calibrators[key].lincal(data[p], additivein, verbose=True)

	#######################save results###############################
	print "Done."
	print FILENAME + " MSG: saving calibration results on %s %s."%(dataano, key)
	#Zaki: catch these outputs and save them to wherever you like
	calibrators[key].utctimes = timing
	calibrators[key].get_calibrated_data(data[p])
	calibrators[key].get_omnichisq()
	calibrators[key].get_omnigain()
	calibrators[key].get_omnifit()