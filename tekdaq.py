#!/usr/bin/env python

import visa
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.ticker import FormatStrFormatter

import math
import time
import sys

#import scopeMethods

rootExists=True

try:
    import ROOT as r
    r.PyConfig.IgnoreCommandLineOptions = True
    from ROOT import TFile, TTree
except ModuleNotFoundError:
    rootExists=False
    
import numpy as np
import argparse

defaultFile="tek.dat"
if rootExists:
    defaultFile="tek.root"

#parse command line arguments
parser = argparse.ArgumentParser("Read data from a Tektronix TDS 3052 oscilloscpe via an RS-232 port")
parser.add_argument('-p','--port', help='The port to listen to', default="/dev/ttyUSB0", required=False)
parser.add_argument('-r','--baudrate', help='baud rate of port', default=38400, required=False)
parser.add_argument('-u','--unlock', help='Unlock front panel then exit', action='store_true', required=False)
parser.add_argument('--nosave', help="Don't save data", action='store_true', required=False)
parser.add_argument('-o','--output', help='Name of data file', default=defaultFile, required=False, metavar='FILE')
parser.add_argument('-n','--nevents', help='Number of events to record. If none specified, runs until closed.', default=-1, required=False)
parser.add_argument('-k','--keep', help='Keep existing scope settings, ignoring other command line arguments.', action='store_true', required=False)
parser.add_argument('-w','--wave', help='Record waveform data for channel CH; specify \'a\' for all channels.', default='a', required=False, metavar='CH', choices=['a','1','2'])
parser.add_argument('-l','--length', help='Specify the waveform recordlength; not independent of the time base. Allowed values are: 5.E2 and 1.E4', default='5.E2', required=False, choices=['5.E2', '1.E4'], metavar="LENGTH")
parser.add_argument('-c', '--trsrc', help='Specify the trigger channel; specify \'0\' for \'EXT\'', default='1', required=False, metavar='CH', choices=['0','1','2'])
parser.add_argument('-t','--trlevel', help='Specify trigger level (in volts).', default='1E0', required=False, metavar='TRIG_LEVEL')
parser.add_argument('-s', '--trslope', help='Specify the trigger edge slope - FALL or RISE.', default='RISE', required=False, metavar='TRIG_SLOPE', choices=['RISE','FALL'])
parser.add_argument('--vsca1', help='Specify vertical scale (in volts) for channel 1.', default= '200E-3', required=False, metavar='VSCALE')
parser.add_argument('--vsca2', help='Specify vertical scale (in volts) for channel 2.', default= '200E-3', required=False, metavar='VSCALE')
parser.add_argument('--coupl1', help='Specify coupling for channel 1, \'AC\' or \'DC\'; default is \'DC\'.',  default='DC', required=False, metavar='COUPL', choices=['AC', 'DC'])
parser.add_argument('--coupl2', help='Specify coupling for channel 2.',  default='DC', required=False, metavar='COUPL', choices=['AC', 'DC'])
parser.add_argument('--imped1', help='Specify impedance for channel 1, \'FIF\' or \'MEG\'; default is \'MEG\'.',  default='MEG', required=False, metavar='IMPED', choices=['FIF', 'MEG'])
parser.add_argument('--imped2', help='Specify impedance for channel 2.',  default='MEG', required=False, metavar='IMPED', choices=['FIF', 'MEG'])
parser.add_argument('-b','--hsamp', help='Specify the horizontal scale (in seconds); note that this can effect the sample rate.', default='20.E-9', required=False)
parser.add_argument('-pt','--pretrigger', help='Specify the amount of pretrigger (percent).', default='20', required=False)


args = parser.parse_args()

if not rootExists:
    print("Root not found. Data will be saved as text files")

#open up the visa manager
rm = visa.ResourceManager('@py')

#connect to scope
tds = rm.open_resource('ASRL'+args.port+'::INSTR')

#set the baud rate
tds.baud_rate = int(args.baudrate)

splitFilename=args.output.split(".")


#unlock the scope if requested
if args.unlock:
    tds.write("LOC NONE")
    exit()
    


# Make the scope identify itself.
print(tds.query('*IDN?'))


vsca1=args.vsca1
vsca2=args.vsca2
hsamp=args.hsamp

getdata = [False, False]

#apply settings if '-k' setting not used
if not args.keep:
    if args.wave == 'a' or args.wave =='1':
        tds.write("CH1:SCA "+args.vsca1)
        tds.write("CH1:COUPL "+args.coupl1)
        tds.write("CH1:IMPED "+args.imped1)
        tds.write("SEL:CH1 ON")
    
    if args.wave == 'a' or args.wave =='2':
        tds.write("CH2:SCA "+args.vsca2)
        tds.write("CH2:COUPL "+args.coupl2)
        tds.write("CH2:IMPED "+args.imped2)
        tds.write("SEL:CH2 ON")

        
    tds.write("TRIGGER:A:LEVEL -1.E-2")
    if args.trsrc == '0':
        tds.write("TRIG:A:EDGE:SOU EXT")
    else:    
        tds.write("TRIG:A:EDGE:SOU CH"+args.trsrc)
    tds.write("TRIG:A:EDGE:SLO "+args.trslope)
        
    tds.write("HOR:SCA "+args.hsamp)
    tds.write("HOR:TRIG:POS "+args.pretrigger)

    
else: #if '-k' used, get the horizontal and vertical scale

    
    tds.write("HORIZONTAL?")
    temp=tds.read()
    hsamp=temp.split(';')[2]

    tds.write("CH1:SCALE?")
    vsca1=tds.read()
    tds.write("CH2:SCALE?")
    vsca2=tds.read()

    

    
tds.write("HOR:RECORDLENGTH "+args.length)    


#set the waveform flags
if args.wave == 'a' or args.wave =='1':
    getdata[0]=True
if args.wave == 'a' or args.wave =='2':
    getdata[1]=True


Preambles = []

tds.write("HEADER OFF");

WFM_PREAMBLE_FIELDS = (
            ('bytes_per_sample', int,),
            ('bits_per_sample', int,),
            ('encoding', str,),
            ('binary_format', str,),
            ('byte_order', str,),
            ('number_of_points', int,),
            ('waveform_id', str,),
            ('point_format', str,),
            ('x_incr', float,),
            ('pt_offset', int,),
            ('xzero', float,),
            ('x_units', str,),
            ('y_scale', float,),
            ('y_zero', float,),
            ('y_offset', float,),
            ('y_unit', str,),
    )
WFM_PREAMBLE_FIELD_NAMES = tuple(f[0] for f in WFM_PREAMBLE_FIELDS)
WFM_PREAMBLE_FIELD_CONVERTERS = tuple(f[1] for f in WFM_PREAMBLE_FIELDS)


#get the waveform preablmes
for ch in range(2):
    if getdata[ch]:
        tds.write("DATA:SOURCE CH"+str(ch+1))
        tds.write("DATA:WIDTH 2")
        tds.write("ENCDG RPBinary")
        tds.write("WDMPRE:PT_Fmt Y")

        tds.write("WFMPRE?")
        wfm = tds.read().split(';')
        pre =dict(zip(
            WFM_PREAMBLE_FIELD_NAMES,
            [WFM_PREAMBLE_FIELD_CONVERTERS[i](wfm[i]) for i in range(len(wfm))]
        ))
        Preambles.append(pre)
    else:
        Preambles.append(0)


tds.write("WFMPRE:NR_PT?")
point_count = int(tds.read())
          
        
#lock the 'scope, set to single seq mode
tds.write("LOC All")
tds.write("ACQ:STOPA SEQ")


vectors=[]
f=""
t=""
xinc = np.zeros(1, dtype=float)

#setup root saving
if rootExists and not args.nosave:
    f=TFile(args.output, 'recreate')
    t=TTree("data", "data")

    #create vectors
    vectors.append(r.vector('double')())
    vectors.append(r.vector('double')())

    #assign branches
    for ch in range(2):
        if getdata[ch]:
            t.Branch('ch'+str(ch+1), vectors[ch])
            
    #assign xincrement branch
    t.Branch('xinc', xinc, 'xinc/D')
    xinc[0]=float(Preambles[0]['x_incr'])
    



#horizontal max and min of graph
xmin=-5*float(hsamp)
xmax=5*float(hsamp)

#vertical max and min of graph
ybase=0.0
if args.wave == '1':
    ybase=5.*float(vsca1)
elif args.wave == '2':
    ybase=5.*float(vsca2)
elif args.wave == 'a':
    ybase=max(5.*float(vsca2),5.*float(vsca1))

ymin=-1.*ybase
ymax=ybase

    
    
# First set up the figure, the axis, and the plot element we want to animate
fig = plt.figure()
ax = plt.axes(xlim=(xmin, xmax), ylim=(ymin, ymax))
lines = []
lobj = ax.plot([], [], 'r-', animated=True)[0]
ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))

#set colours of each waveform
plotlays, plotcols, plotstyle, linw = [2], ["#DCBF73","#6E95B4"], ['', ''], [2,2]

for index in range(2):
    lobj = ax.plot([],[],lw=linw[index], marker=plotstyle[index],color=plotcols[index])[0]
    lines.append(lobj)



# initialization function: plot the background of each frame
def init():
    for i in range(2):
        lines[i].set_data([],[])
    return lines

# close the scope and file
def finished():
    global rootExists

    if rootExists and not args.nosave:
        f.Write()
        f.Close()
    
    tds.write("LOC NONE")
    
    tds.close()
    exit()


    
#write an event to file
def writeEvent(lines=[]):

    global numEvents

    #root file writing
    if rootExists:
        for ch in range(2):
            if getdata[ch]:
                vectors[ch].clear()
                x,data=lines[ch].get_data()
                for pt in data:
                    vectors[ch].push_back(pt)
        t.Fill()

    #text file writing
    else:
        x1,ch1=lines[0].get_data()
        x2,ch2=lines[1].get_data()

        try:
            l=len(x1)
            x=x1
        except TypeError:
            l=len(x2)
            x=x2

        
        with open(splitFilename[0]+"_"+str(numEvents)+"."+splitFilename[1], 'w') as f:
            for i in range(l):
                f.write('{:0.3e}'.format(x[i]))
                if getdata[0]:
                    f.write("\t"+"{0:.9f}".format(round(ch1[i],9)))
                
                if getdata[1]:
                    f.write("\t"+"{0:.9f}".format(round(ch2[i],9))+"\n")
                else:
                    f.write("\n")
                    
                

numEvents=0

# animation function.  This is called sequentially
def animate(i):
    global numEvents
    global rootExists


    # exit on end of run
    if int(args.nevents)!=-1:
        if numEvents >= int(args.nevents):
            finished()
    
    numEvents = numEvents+1

    global t
    global vectors
    global Preambles

    #set acquire state
    tds.write("ACQ:STATE ON")

  
    #get curves
    for ch in range(2):
        if getdata[ch]:
            tds.write("DATA:SOURCE CH"+str(ch+1))
            
            curve = tds.query_binary_values('CURVE?', datatype='H', is_big_endian=True)
                
            #use waveform header to convert ADC counts to volts
            waveform = (
                (float(Preambles[ch]["xzero"]) + i*float(Preambles[ch]["x_incr"]), ((curve[i] - float(Preambles[ch]["y_offset"])) * float(Preambles[ch]["y_scale"])) + float(Preambles[ch]["y_zero"]))
                for i in range(len(curve))
            )
            
            xdat=[]
            ydat=[]

            #add data to graph and root file
            for x,y in waveform:
                xdat.append(x)
                ydat.append(y)

            lines[ch].set_data(xdat,ydat)  
        else:
            lines[ch].set_data(0,0)

    
    if not args.nosave:
        writeEvent(lines)
    return lines




# call the animator.  blit=True means only re-draw the parts that have changed.
anim = animation.FuncAnimation(fig, animate, init_func=init,
                               frames=20, interval=20, blit=True)


tds.write("WFMPRE:XUNIT?")
plt.xlabel(tds.read()[1])

tds.write("WFMPRE:YUNIT?")
plt.ylabel(tds.read()[1])

plt.show()

finished()



