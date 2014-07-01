#!/usr/bin/env python

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

ap.scripting.add_standard_options(o, cal=True, pol=False)
o.add_option('-o', '--path', action = 'store', default = '', help = 'output name with path')
o.add_option('-e', '--tol', action = 'store', type = 'float', default = 1e-2, help = 'tolerance of antenna location deviation when computing unique baselines.')
o.add_option('--ba', action = 'store', default = '', help = 'bad antenna number indices seperated by commas')
o.add_option('--bu', action = 'store', default = '', help = 'bad unique baseline indices seperated by commas')
o.add_option('--overwrite', action = 'store_true', help = 'overwrite if file exists')
opts,args = o.parse_args(sys.argv[1:])

if opts.path == '':
	raise Exception('Error: no output filename specified! Use -o to specify full name and path.')
#if os.path.isfile(opts.path):
	#raise Exception('Error: output filename exists!')

aa = ap.cal.get_aa(opts.cal, np.array([.15]))

try:
	badAntenna = [int(i) for i in opts.ba.split(',')]
except:
	badAntenna = []
try:
	badUBL = [int(i) for i in opts.bu.split(',')]
except:
	badUBL = []
print 'Bad Antennas:', badAntenna
print 'Bad unique baselines:', badUBL

calibrator = RedundantCalibrator_PAPER(aa)
calibrator.compute_redundantinfo(badAntenna = badAntenna, badUBL = badUBL, antennaLocationTolerance = opts.tol)
calibrator.write_redundantinfo(infoPath = opts.path, overwrite = opts.overwrite)

