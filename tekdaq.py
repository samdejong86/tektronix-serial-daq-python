from serial import Serial
from pytek.pytek import TDS3k
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.ticker import FormatStrFormatter

import math
import time
import argparse
import sys

import ROOT as r
from ROOT import TFile, TTree, AddressOf, gROOT
import numpy as np


parser = argparse.ArgumentParser("Read data from a Tektronix TDS 3052 oscilloscpe via an RS-232 port")
parser.add_argument('-p','--port', help='The port to listen to', default="/dev/ttyUSB0", required=False)
parser.add_argument('-r','--baudrate', help='baud rate of port', default=38400, required=False)

parser.add_argument('-u','--unlock', help='Unlock front panel then exit', action='store_true', required=False)

parser.add_argument('-o','--output', help='Name of data file', default="tek.root", required=False, metavar='FILE')
parser.add_argument('-k','--keep', help='Keep existing scope settings, ignoring other command line arguments.', action='store_true', required=False)
parser.add_argument('-w','--wave', help='Record waveform data for channel CH; specify \'a\' for all channels.', default='a', required=False, metavar='CH', choices=['a','1','2'])
parser.add_argument('-l','--length', help='Specify the waveform recordlength; not independent of the time base. Allowed values are: 5.E2 and 1.E4', default='5.E2', required=False, choices=['5.E2', '1.E4'])
parser.add_argument('-n','--nevents', help='Number of events to record', default='10', required=False)
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

port = Serial(args.port, args.baudrate, timeout=1)
tds = TDS3k(port)

if args.unlock:
    tds.send_command("LOC NONE")
    exit()
    


# Make the scope identify itself.


vsca1=args.vsca1
vsca2=args.vsca2
hsamp=args.hsamp

print(tds.identify())

getdata = [False, False]

if not args.keep:
    if args.wave == 'a' or args.wave =='1':
        tds.send_command("CH1:SCA "+args.vsca1)
        tds.send_command("CH1:COUPL "+args.coupl1)
        tds.send_command("CH1:IMPED "+args.imped1)
        tds.send_command("SEL:CH1 ON")
    
    if args.wave == 'a' or args.wave =='2':
        tds.send_command("CH2:SCA "+args.vsca2)
        tds.send_command("CH2:COUPL "+args.coupl2)
        tds.send_command("CH2:IMPED "+args.imped2)
        tds.send_command("SEL:CH2 ON")

        
    tds.send_command("TRIGGER:A:LEVEL -1.E-2")
    if args.trsrc == '0':
        tds.send_command("TRIG:A:EDGE:SOU EXT")
    else:    
        tds.send_command("TRIG:A:EDGE:SOU CH"+args.trsrc)
    tds.send_command("TRIG:A:EDGE:SLO "+args.trslope)
        
    tds.send_command("HOR:SCA "+args.hsamp)
    tds.send_command("HOR:TRIG:POS "+args.pretrigger)

else:
    temp=tds.send_query("HORIZONTAL")
    hsamp=temp.split(';')[2]
    
    vsca1=tds.send_query("CH1:SCALE")
    vsca2=tds.send_query("CH2:SCALE")

tds.send_command("HOR:RECORDLENGTH "+args.length)    


if args.wave == 'a' or args.wave =='1':
    getdata[0]=True
if args.wave == 'a' or args.wave =='2':
    getdata[1]=True
    

Preambles = []

for ch in range(2):
    if getdata[ch]:
        c1=tds.get_curve("CH"+str(ch+1))
        Preambles.append(tds.get_waveform_preamble())
    else:
        Preambles.append(0)


tds.send_command("LOC All")
tds.send_command("ACQ:STOPA SEQ")



xmin=-5*float(hsamp)
xmax=5*float(hsamp)


ybase=0.0
if args.wave == '1':
    ybase=5.*float(vsca1)
elif args.wave == '2':
    ybase=5.*float(vsca2)
elif args.wave == 'a':
    ybase=max(5.*float(vsca2),5.*float(vsca1))


    

ymin=-1.*ybase
ymax=ybase

f=TFile(args.output, 'recreate')
t=TTree("data", "data")

vectors=[]
vectors.append(r.vector('double')())
vectors.append(r.vector('double')())

for ch in range(2):
    if getdata[ch]:
        t.Branch('ch'+str(ch+1), vectors[ch])

        
xinc = np.zeros(1, dtype=float)
t.Branch('xinc', xinc, 'xinc/D')
xinc[0]=float(Preambles[0]['x_incr'])

        

    
    
# First set up the figure, the axis, and the plot element we want to animate
fig = plt.figure()
ax = plt.axes(xlim=(xmin, xmax), ylim=(ymin, ymax))
lines = []
lobj = ax.plot([], [], 'r-', animated=True)[0]
ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
#ax.xaxis.set_major_formatter(FormatStrFormatter('%.2f'))


plotlays, plotcols, plotstyle, linw = [2], ["#DCBF73","#6E95B4"], ['', ''], [2,2]

for index in range(2):
    lobj = ax.plot([],[],lw=linw[index], marker=plotstyle[index],color=plotcols[index])[0]
    lines.append(lobj)



# initialization function: plot the background of each frame
def init():
    for i in range(2):
        lines[i].set_data([],[])
    return lines


numEvents=0

# animation function.  This is called sequentially
def animate(i):

    global numEvents
    numEvents = numEvents+1

    global t
    global vectors

    if i > numEvents:
        return lines

    global Preambles;

    tds.send_command("ACQ:STATE ON")
    
    for ch in range(2):
        if getdata[ch]:
            curve = tds.get_curve("CH"+str(ch+1))
            data = (
                (float(Preambles[ch]["xzero"]) + i*float(Preambles[ch]["x_incr"]), ((curve[i] - float(Preambles[ch]["y_offset"])) * float(Preambles[ch]["y_scale"])) + float(Preambles[ch]["y_zero"]))
                for i in range(len(curve))
            )

            
            xdat=[]
            ydat=[]

            vectors[ch].clear()
            for x,y in data:
                xdat.append(x)
                ydat.append(y)
                vectors[ch].push_back(y)

            lines[ch].set_data(xdat,ydat)     

            t.Fill()
            
        else:
            lines[ch].set_data(0,0)
                
    return lines




# call the animator.  blit=True means only re-draw the parts that have changed.
anim = animation.FuncAnimation(fig, animate, init_func=init,
                               frames=int(args.nevents), interval=20, blit=True)



plt.ylabel(tds.y_units())
plt.xlabel(tds.x_units())
plt.show()

f.Write()
f.Close()


tds.send_command("LOC NONE")

tds.close()
