from serial import Serial
from pytek import TDS3k
import matplotlib.pyplot as plt
import matplotlib.animation as animation


import argparse
import sys

parser = argparse.ArgumentParser("Read data from a Tektronix TDS 3052 oscilloscpe via an RS-232 port")
parser.add_argument('-p','--port', help='The port to listen to', default="/dev/ttyUSB0", required=False)
parser.add_argument('-r','--baudrate', help='baud rate of port', default=38400, required=False)

parser.add_argument('-o','--output', help='Name of data file', default="tek.dat", required=False, metavar='FILE')
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


# Make the scope identify itself.


print(tds.identify())

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

    
tds.send_command("HOR:RECORDLENGTH "+args.length)



xmin=-5*float(args.hsamp)
xmax=5*float(args.hsamp)


ybase=0.0
if args.wave == '1':
    ybase=5.*float(args.vsca1)
elif args.wave == '2':
    ybase=5.*float(args.vsca2)
elif args.wave == 'a':
    ybase=max(5.*float(args.vsca2),5.*float(args.vsca1))
    

ymin=-1.*ybase
ymax=ybase
    
    
# First set up the figure, the axis, and the plot element we want to animate
fig = plt.figure()
ax = plt.axes(xlim=(xmin, xmax), ylim=(ymin, ymax))
lines = []
lobj = ax.plot([], [], 'r-', animated=True)[0]



plotlays, plotcols, plotstyle, linw = [2], ["#DCBF73","#6E95B4"], ['', ''], [2,2]

numPlots=1
if args.wave=='a':
    numPlots=2

for index in range(2):
    lobj = ax.plot([],[],lw=linw[index], marker=plotstyle[index],color=plotcols[index])[0]
    lines.append(lobj)



# initialization function: plot the background of each frame
def init():
    for i in range(numPlots):
        lines[i].set_data([],[])
    return lines


numEvents=0

# animation function.  This is called sequentially
def animate(i):

    global numEvents
    numEvents = numEvents+1
    
    if args.wave != 'a':
        xdat=[]
        ydat=[]
    
        waveform = []
        if args.wave == '1':
            waveform = tds.get_waveform("CH1")
        if args.wave == '2':
            waveform = tds.get_waveform("CH2")
                        
        for x,y in waveform:
            #print(str(x)+" "+str(y))
            xdat.append(x)
            ydat.append(y)
        
            
        lines[0].set_data(xdat,ydat)         

    else:
        xdat=[]
        ydat1=[]
        ydat2=[]
        waveform1=tds.get_waveform("CH1")
        waveform2=tds.get_waveform("CH2")
        
        for x,y in waveform1:
            xdat.append(x)
            ydat1.append(y)

        for x,y in waveform2:
            ydat2.append(y)
            
        lines[0].set_data(xdat, ydat1)
        lines[1].set_data(xdat, ydat2)       

        

    return lines




# call the animator.  blit=True means only re-draw the parts that have changed.
anim = animation.FuncAnimation(fig, animate, init_func=init,
                               frames=int(args.nevents), interval=20, blit=True)



plt.ylabel(tds.y_units())
plt.xlabel(tds.x_units())
plt.show()



tds.close()
