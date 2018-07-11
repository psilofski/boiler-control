#!/usr/bin/python

import sqlite3 as sql
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date

fmt = '%Y-%m-%d %H:%M:%S'
db_data = '/home/pi/thermo-dev/data/tempResearch_2018.db'
#db_params = 'data/parameters.db'
conn = sql.connect(db_data)

with conn:
    c = conn.cursor()
    c.execute( '''SELECT * FROM sensors order by rowid desc limit 3000;''' )
    data_temps = c.fetchall()

conn.close()
dates = []
temps = []
th1 = []
th2 = []
th_on = timedelta(0)
data = list( reversed( data_temps ) )
th_toplot = [0, None] #float('nan')] #[on, off]
for row in data:
    dates.append( datetime.strptime(row[0], fmt) )
    if row[3] > 0:
        temps.append(row[3])
    elif temps[-1] > 0:
        temps.append( temps[-1] )
    else:
        temps.append( temps[-2] )
    th1.append(th_toplot[row[10]])
    th2.append(th_toplot[row[11]])

#    if th1[-1] == 0:
#        th_on.append(dates[-1])
    
    try:
        if th1[-1] == 0 or ( th1[-1] == 1 and th1[-2] == 0 and (dates[-1]-dates[-2]).total_seconds()<240 ):
            th_on = th_on + ( dates[-1] - dates[-2] )
            #th_on.append(dates[-1])
            #th_on.append(dates[-1])
    except IndexError:
        pass
total_days = dates[-1] - dates[0]
print dates[0].strftime(fmt)
print 'total On time: ', th_on
mean_min = 'Boilers On per day: ' + repr( round( th_on.total_seconds() / total_days.days / 60 ) ) + ' min'
print mean_min
print 'Power cost: ', th_on.total_seconds() / 3600*8*0.20

#    print dates, temps, th1, th2   #debug
nowstamp = datetime.now()
#nowstamp = datetime(2018, 7, 11, 16, 0) #debug

fig = plt.figure()
ax = fig.add_subplot(111)
ax.plot(dates, temps)
ax.grid('True', 'minor', 'x', color='r', linestyle='-', linewidth=0.2)
ax.grid('True', 'major', 'y', color='r', linestyle='-', linewidth=0.2)
ax.set_xlabel('Hour')
ax.set_ylabel('Water Temp (C)')
ax.text(0.3, 0.7, mean_min, rotation=45, horizontalalignment='center', verticalalignment='top', multialignment='center',transform=fig.transFigure)
ax.set_xlim(dates[0], nowstamp)
#ax.text(0.5 ,0.5 ,'kslaklskalsa',transform=fig.transFigure)
ax1 = fig.add_subplot(20,1,1)
ax1.plot(dates, th1, 'ro')
ax1.set_yticklabels( ['on'], fontsize=10 )
ax1.set_xlim(dates[0], nowstamp)
# format your data to desired format. Here I chose YYYY-MM-DD but you can set it to whatever you want.
import matplotlib.dates as mdates
ax.xaxis.set_major_formatter(mdates.DateFormatter('%H'))

#ax.xaxis.set_major_locator(dates.HourLoc3tor(byhour=range(0,24,1)))
locator = mdates.HourLocator(byhour=range(0,24,1))
ax.xaxis.set_minor_locator(locator)
ax1.xaxis.set_ticks_position('both')

# rotate and align the tick labels so they look better
fig.autofmt_xdate()

fig.savefig('/home/pi/www/data/daily.png')
#plt.plot(dates, temps)
#plt.legend()







