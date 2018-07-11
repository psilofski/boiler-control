#!/usr/bin/python

# Check Thermos every !led_blink_rate sec, write to db every !db_post_rate sec 
# Each_Hour, turn off heater relays at Tth1_limit[Hour] oC
# Turn on output heater:
#       if limit - Tth1 > Tdiff_med (5oC)
# Turn on input heater:
#       if limit - Tth1 > Tdiff_high (15oC)
#       if Tth1 is falling fast - more than !Tdrop (compared to last db entry)
# Turn off input heater:
#       if in Tdiff_med range, but Tth1 is rising
#
# Thermos state is f(GPIO state) :
# GPIO = 1 -> Thermos are off
#
# Arduino on boilers is transmitting following data:
# T1 = onboard temperature
# T3 = East (first) solar heater temperature
# T4 = environmental temperature
# T2 = West (second) solar heater temperature
# Light = (sensor is missing yet)
#
# Reading serial of arduino on power rails (115200 baud):
# 'I1 I2 I3\r\n'

import urllib2, errno, socket, sqlite3, json
import serial
from datetime import datetime, timedelta, date
from time import sleep, time
#from get_thermo_data import fetch_sensors, db_enter
from defcollection import sendreport, logme
import RPi.GPIO as GPIO

path_user = '/home/pi/'
path_www = path_user + 'www/'
db_param_file = path_user + 'thermo-dev/data/parameters.db'

path_data = path_user + 'thermo-dev/data/'
#path_log = path_data + 'log/'
logfile_info = path_data + 'info.log'
logfile_error = path_data + 'error.log'

emailing = 1 #sending email notifications
email_recipient = 'info@klerystudios.gr'
#Hour of day:[ 0, 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15,
#       16, 17, 18, 19, 20, 21, 22, 23 ]
Tth1_limit_default = [55, 49, 49, 49, 49, 49, 55, 55, 55, 55, 55, 49, 49, 49, 49, 50,
        50, 50, 55, 55, 55, 55, 55, 55]

#timer: times to turn on when arduino is down:
timer_morning = ( datetime.strptime('7', '%H').time(), datetime.strptime('8', '%H').time() )
timer_night = ( datetime.strptime('21', '%H').time(), datetime.strptime('22:30', '%H:%M').time() )

Dth1 = 'T2'
Dth2 = 'T3'
lDin = 17
rDin = 9
check1 = 26 #pin for checking if main power is ok
Tdiff_med = 5 #turn on boilers if DifferentialTemperature larger than that
Tdiff_2nd = 10
# I will turn on the boilers for 7 minutes and 5 minutes off, so that the 40A switches cool down:
Ton = 1200 #420 #sec
Toff = 120 #300 #sec
th1_on_time = 0
th2_on_time = 0
th1_off_time = datetime(2015, 1, 1)
th2_off_time = datetime(2015, 1, 1)
#Tdiff_high = 10
Tdrop = 2
db_post_rate = 60 #sec
led_blink_rate = 4 #sec, higher will cause loop delay, as the loop is paused for the led to blink
Tsensor_sampling_rate = 3 #every these seconds read T sensors
utimeout = 20 #sec, timeout for urlRequests

#Power reading parameters:
fuse_to_th1 = 0
fuse_to_th2 = 1
fuse_to_th3 = 2
T_fuse_maximum = 76**2*100.0 #(76**2 + 41**3)*50 # Cut off at 100sec on 76A (really 106sec)
fuse_reset = 0.9 # fuse_reset*T_fuse_maximum
th1_cutted = 0
th2_cutted = 0
#T_fuse = [T_fuse_maximum for i in range(5)]
#Can dissipate 40A when hot, so:
fuse_rating = 35
thermal_dissipation_coeff = fuse_rating**2/T_fuse_maximum #(40**2 + 5**3)/ T_fuse_maximum # k*(surface area)/(thickness)
T_fuse = [20**2/thermal_dissipation_coeff for i in range(3)] # Initialise supposing 20A continuous I before
timer_power = time()

fmt = '%Y-%m-%d %H:%M:%S'
#Initialising serial input for power readings from Arduino
try:
    ser = serial.Serial('/dev/ttyACM0', 115200)
except serial.serialutil.SerialException, e:
    try:
        ser = serial.Serial('/dev/ttyACM1', 115200)
    except serial.serialutil.SerialException, e:
        logme(e, logfile_error)
        print datetime.now().strftime(fmt) + ' Serial port read Error'


# Set GPIO enumeration as BCM for universal lang compatibility
GPIO.setmode(GPIO.BCM)
# Relay part (2 available)
GPIO.setup(lDin, GPIO.OUT) #17
GPIO.setup(rDin, GPIO.OUT) #9
# Switch control part (1 available)
GPIO.setup(check1, GPIO.IN, pull_up_down=GPIO.PUD_UP) #26, GPIO is grounded if switch
# open
# Information led
GPIO.setup(10, GPIO.OUT)


# Calculate fuses Temperature from I readings:
def normalise_T(data):
    return data/T_fuse_maximum*100


def fetch_crowd(hdate):
    #    req = urllib2.Request( "http://klerystudios.gr/cgi-bin/todays_crowd.py?date=" + hdate.strftime('%Y-%m-%d') )
#    res = urllib2.urlopen(req, None, utimeout)
    ### until I fix daily numbers:
    url = "https://www.beds24.com/api/json/getAvailabilities"
    date_current = date.today().strftime('%Y%m%d')
    data = json.dumps( {'checkIn': date_current, 'lastNight': date_current, 'propId': '16673'} )
    req = urllib2.Request( url, data, {'Content-Type': 'application/json'} )
    f = urllib2.urlopen(req)
    response = json.loads( f.read() )
    f.close()

    counter = 12 #total no of rooms, will deduct available ones
    for key in response:
        try:
            counter = counter - int( response[key]['roomsavail'] )
        except TypeError:
            pass

    return counter #float(res.read())

def fetch_sensors():
    req = urllib2.Request("http://192.168.88.201:90")
    res = urllib2.urlopen(req, None, utimeout)

    html = res.read()
#    data =  html.decode()

#    print data #debug

    sensorRow = html.split('<BODY>\r\n')[1].split('<br />')
    sensors = {}
    for sensor in sensorRow:
        foo = sensor.split(':')
        sensors[foo[0]] = foo[1]

    return sensors

def db_enter(power_matrix, sensors, T_fuse, powerIn_state, th1_state=0, th2_state=0):

    timestamp = datetime.now().strftime(fmt)
    T1 = sensors['T1']
    T2 = sensors['T2']
    T3 = sensors['T3']
    T4 = sensors['T4']
    Light = sensors['Light']
    Tfuse1 = T_fuse[fuse_to_th1]
    Tfuse2 = T_fuse[fuse_to_th2]
    Tfuse3 = T_fuse[fuse_to_th3]
    
    db_filename = path_data + './tempResearch_' + datetime.now().strftime('%Y') + '.db'
    conn = sqlite3.connect(db_filename)

    with conn:
        c = conn.cursor()
        c.execute( '''CREATE TABLE IF NOT EXISTS sensors
            (timestamp text, Light real, T1 real, T2 real, T3 real, T4 real, Tfuse1 real, Tfuse2 real, Tfuse3 real, powerIn_state integer, th1_state integer, th2_state integer) ''')
        c.execute( '''INSERT INTO sensors VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?)''', (timestamp, Light, T1, T2, T3, T4, Tfuse1, Tfuse2, Tfuse3, powerIn_state, th1_state, th2_state) )

        c.execute( '''CREATE TABLE IF NOT EXISTS power
            (timestamp text, L1 real, L2 real, L3 real) ''')
        for i in power_matrix:
            c.execute( '''INSERT INTO power VALUES
                (?,?,?,?)''', ( [j for j in i] ) )
 
    conn.close()
#    print 'data entered in db!' #debug

def th1_switch(state):
    GPIO.output(rDin, state)
#   print 'th1 switch set to:', state   #debug
    return state

def th2_switch(state):
    GPIO.output(lDin, state)
#   print 'th2 switch set to:', state   #debug
    return state

def seconds_from(times):
    try:
        res = int( repr(datetime.now() - times).split(', ')[1] )
    except:
        res = 0
    return res

#def V220():
#    return GPIO.input(26)

def blink(speed):
    for i in range (1, speed * led_blink_rate):
        GPIO.output(10, True)
        sleep(0.1)
        GPIO.output(10, False)
        sleep(1/speed)

fmt = '%Y-%m-%d %H:%M:%S'
post_now = 1 #make a db post on first run
prev_check = 0
crowd = {} #accounting for fullness
run_date = datetime.now().date()
dbposttime = datetime.now() #fake, for avoiding error in next if
Tsensor_read_time = time() - 10 #Allow first read to happen anyway
th1_state = [1, th1_switch(1)] #previous and current state
th2_state = [1, th2_switch(1)]
set1_state = 1
set2_state = 1
boolean_state = ['on', 'off'] #0 means on, 1 means off, used in reporting
serialhelper = {'I1': 0, 'I2': 1, 'I3':2} #according to railDuino serial output
data = [0, 0, 0] #initialise serial data read

logme( datetime.now().strftime(fmt) + 'Solar Heater Control starts now!', logfile_info )
try:
    while True:

        try: #reading from parameters sql in case of changes from www
            conn_param = sqlite3.connect(db_param_file)
            with conn_param:
                c = conn_param.cursor()

                c.execute( '''SELECT * FROM temperatures order by rowid desc limit 1;''' )
                data_temps = c.fetchone() #[H00, H01,...,H23,timestamp]
                c.execute( '''SELECT * FROM toggles order by rowid desc limit 1;''' )
                data_toggles = c.fetchone() #[manual (m/a), th1, th2, timestamp]

            conn_param.close()
            Tth1_limit = data_temps[:-1]

        except sqlite3.Error:
            Tth1_limit = Tth1_limit_default #Setting default temperature limits
            data_toggles = ['a', 1, 1, 'timestamp'] #only [0] needed, setting automatic control 

            
        present = datetime.now()
        hoteldate = ( present - timedelta( present.strftime('%H') <= '14' ) ).date()#True = 1, False = 0
        try:
            full_rooms = crowd[hoteldate]
        except KeyError:
            try:
                crowd[ hoteldate ] = fetch_crowd(hoteldate)
                full_rooms = crowd[hoteldate]
                logme( 'todays Nof full rooms: ' + repr(int(full_rooms)), logfile_info )
    #           print full_rooms #debug
            except urllib2.URLError, e:
                full_rooms = 12 #on fatal Error, take the worst case
                logme('Connection with no of  rooms counter: ' + repr(e), logfile_error)
        lt_perday = (full_rooms*2.5+3)*25
        Tdiff_high = Tdiff_2nd * ( 1 - 1/2.0*( lt_perday / ( (12*2.5+3)*25 ) ) )
#        print Tdiff_high #debug
#        Tdiff_high = 10 #debug

        #Connect to thermo arduino every Ts_s_r seconds:
        if time() - Tsensor_read_time > Tsensor_sampling_rate :

            try:
                try:
                    sensors_dict = fetch_sensors()
                except socket.timeout, e:
                    logme( e, logfile_error )
                #sleep(0.4)
                Tth1 = float( sensors_dict[Dth1] )
                Tth2 = float( sensors_dict[Dth2] )
#If I get T1 = -127.0, try a second time:                
                if Tth1 < 0:
                    sensors_dict = fetch_sensors()
                    Tth1 = float( sensors_dict[Dth1] )
                    Tth2 = float( sensors_dict[Dth2] )

                Tsensor_read_time = time()

                try:
                    if Tth1<36 and Tth1>0 and not T_before_cold:
                        msg = 'Water is getting Cold: ' + repr(Tth1) + ' oC'
                        post_now = 1
                        logme(msg, logfile_info)
                        if emailing: sendreport(email_recipient, 'cold water', msg)
                        T_before_cold = 1
                    elif Tth1 >= 36:
                        T_before_cold = 0
                except NameError:
                    T_before_cold = 1

            except urllib2.URLError,e: #lost connection to arduino, will work as a timer
                tnow = present.time()
                if (tnow>timer_morning[0] and tnow<timer_morning[1]) or (tnow>timer_night[0] and tnow<timer_night[1]):
                    Tth1 = 1 #to turn heaters on
                    Tth2 = 1
                else:
                    Tth1 = 99 #to turn heaters off
                    Tth2 = 99

                logme('Heater thermostat: ' + repr(e), logfile_error)
                print 'No connection to Solar Heaters Thermometer!'



        hour = int(present.strftime('%H'))

#       if seconds_from(th1_on_time) > Ton or seconds_from(th1_off_time) < Toff:
#           th1_state[1] = th1_switch(1)
#           th1_off_time = datetime.now()
#           if seconds_from(th2_on_time) > Ton or seconds_from(th2_off_time) < Toff:
#               th2_state[1] = th2_switch(1)
#               th2_off_time = datetime.now()
#       else:

        Tth1_diff =  Tth1_limit[hour] - Tth1
        if Tth1_diff > Tdiff_med:
            set1_state = 0
#                th1_state[1] = th1_switch(0)
#                th1_on_time = datetime.now()
            if Tth1_diff > Tdiff_high: #or Tth1_bias > Tdrop:
                set2_state = 0
#                    th2_state[1] = th2_switch(0)
#                    th2_on_time = datetime.now()

#       elif Tth1_bias < 0:
#           th2_state = th2_switch(1)

#        print set1_state, seconds_from(th1_on_time), seconds_from(th1_off_time) #debug

        if Tth1_diff <= 0:
            set1_state = 1
            set2_state = 1
#           th1_state[1] = th1_switch(1)
#           th1_off_time = datetime.now()
#           th2_state[1] = th2_switch(1)
#           th2_off_time = datetime.now()

#       Calculating T of fuses by reading I:
        try:
            # data = ser.readline().split('\r')[0].split(' ') # I want to avoid serial.readline()
            for i in range(10): #loop up to 10 times for a real reading
                #data = ser.read(36).split('\r\n')[1].split(' ') # not serial.readline, but is the data correct???
                #data = ser.readline().split('\r')[0].split(' ')
                serialdata = ser.readline().split(';')
                for i in serialdata:
                    foo = i.split('=')
                    #print 'foo: ', foo #debug 
                    if foo[0] in serialhelper:
                        data[serialhelper[ foo[0] ] ]= foo[1]; #ex. foo = ['I1', '0.10']

                #print 'L1 L2 L3: ', data #debug

                if len(data) == 3:
                    break
                else:
                    sleep(0.1)
                    print data, 'Garbled!' #debug

            try:
                power_matrix.append( [datetime.now().strftime(fmt)] + data)
                #print 'power_matrix: ', power_matrix #debug
            except NameError, e: #initialise power_matrix
                power_matrix = [ [datetime.now().strftime(fmt)] + data ]
                print 'Initialising power_matrix: ', power_matrix #debug
            #data = [50.0, 60.0, 76.0] #debug
            time_elapsed = time() - timer_power
            # heat = [ (float(i) - 35)**3 for i in data] #current cause on fuse estimate function
            for i in range( len(data) ):
                # Rate of (kind of) T_fuse increase:
                generate = float(data[i])**2 #+  ( max( 0, float(data[i]) - 35 ) )**3
                dissipate = T_fuse[i] * thermal_dissipation_coeff
                heat = generate - dissipate
                T_fuse[i] = T_fuse[i] + heat*time_elapsed
    #            T_fuse[i] = max( T_fuse[i], 0 )

            timer_power = timer_power + time_elapsed

        except ValueError, e: #if read serial gets garbage data
            print 'Serial read: ', e #debug
            logme(e, logfile_error)
        except IndexError, e: #garbage data from serial
            print 'Serial read: ', e #debug
            logme(e, logfile_error)
        except serial.SerialException, e:
            print 'Serial read: ', e #debug
            logme(e, logfile_error)
            msg = present.strftime(fmt) + ' Serial port read Error'
            print msg
        except OSError, e:
            print 'Serial read: ', e #debug
            logme(e, logfile_error)
            msg = present.strftime(fmt) + ' OS Error due to serial port conflict'
            print msg
        except NameError: #serial is disconnected
            print 'Serial read: ', e #debug
            power_matrix = [[0, 0, 0, 0]] #devel, workaround

#        try: print data, [normalise_T(i) for i in T_fuse] #debug
#        except: pass #debug

# Cut power to boilers for T_fuse  > 0.9*T_max ~ T_max
        if T_fuse[fuse_to_th1] > T_fuse_maximum:
            set1_state = 1
            th1_cutted = 1
        elif T_fuse[fuse_to_th1] < fuse_reset * T_fuse_maximum:
            th1_cutted = 0
        elif th1_cutted == 1:
            set1_state = 1

        if T_fuse[fuse_to_th2] > T_fuse_maximum:
            set2_state = 1
            th2_cutted = 1
        elif T_fuse[fuse_to_th2] < fuse_reset * T_fuse_maximum:
            th2_cutted = 0
        elif th2_cutted == 1:
            set2_state = 1

# Checking if boilers are manually set:
        if data_toggles[0] == 'm':
            set1_state = data_toggles[1]
            set2_state = data_toggles[2]

# Actually setting the relays: #Is this OK ??????
        th1_state[1] = th1_switch(set1_state)
        th2_state[1] = th2_switch(set2_state)

## Turning on and off the boilers to allow time for the fuses to cool down (if I do not have power readings)
#        if not set1_state and seconds_from(th1_on_time) < Ton and seconds_from(th1_off_time) > Toff:
#            th1_state[1] = th1_switch(0)
#        else:
#            th1_state[1] = th1_switch(1)
#
#        if not set2_state and seconds_from(th2_on_time) < Ton and seconds_from(th2_off_time) > Toff:
#            th2_state[1] = th2_switch(0)
#        else:
#            th2_state[1] = th2_switch(1)


        # if we are swiching the boiler state:
        if th1_state[1] != th1_state[0]:
            logme( present.strftime(fmt) + ' T1/2: ' + repr(Tth1) + '/' + repr(Tth2) + ' | Therm1 set to: '+ boolean_state[ th1_state[1] ], logfile_info )
            print 'toggling therm1 ', boolean_state[ th1_state[1] ] #verbose
            post_now = 1
            if not th1_state[1]:
                th1_on_time = datetime.now()
                th1_off_time = datetime(2015, 1, 1)
            else:
                th1_off_time = datetime.now()
                th1_on_time = 0

        if th2_state[1] != th2_state[0]:
            logme( present.strftime(fmt) + ' T1/2: ' + repr(Tth1) + '/' + repr(Tth2) + ' | Therm2 set to: '+ boolean_state[ th2_state[1] ], logfile_info )
            print 'toggling therm2 ', boolean_state[ th2_state[1] ] #verbose
            post_now = 1
            if not th2_state[1]:
                th2_on_time = datetime.now()
                th2_off_time = datetime(2015, 1, 1)
            else:
                th2_off_time = datetime.now()
                th2_on_time = 0

        th1_state[0] = th1_state[1]
        th2_state[0] = th2_state[1]

        #Blink(speed)
        powerIn_state = GPIO.input(check1) #Checking if main power is down
        if not powerIn_state:
            #blink(1)
            if prev_check == 1:
                msg = present.strftime(fmt) + ' Solar heaters power on...'
                post_now = 1
                logme(msg, logfile_info)
                if emailing: sendreport(email_recipient, 'power ok', msg) 
                prev_check = 0
        else:
            #blink(2)
            if prev_check == 0:
                msg = present.strftime(fmt) + ' Solar heaters power down!!!'
                post_now = 1
                logme(msg, logfile_info)
                if emailing: sendreport(email_recipient, 'power Failure', msg)
                prev_check = 1

#if db_post_rate sec have passed since last db postage or I wand specifically to post, post it!
        time_elapsed = datetime.now() - dbposttime #.strftime('%S')
        if time_elapsed.seconds > db_post_rate  or post_now:
            print 'DB post now: ', ('scheduled', 'forced')[post_now] #info
            try:
                db_enter(power_matrix, sensors_dict, [round( normalise_T(i), 3 ) for i in T_fuse], powerIn_state, th1_state[1], th2_state[1])
                power_matrix = []
            except sqlite3.OperationalError, e: # database is locked
                logme( e, logfile_error )
                print e
            except sqlite3.ProgrammingError, e: # garbled data (bigger matrix) from serial
                logme( e, logfile_error )
                print e

#            print present.strftime(fmt), [sensors_dict[i] for i in sensors_dict], [ round( normalise_T(i), 3 ) for i in T_fuse ], powerIn_state, th1_state[1], th2_state[1] #debug
            dbposttime = datetime.now()
            try:
                Tth1_bias = Tth1 - Tth1_past
                Tth2_bias = Tth2 - Tth2_past
            except NameError:
                pass #first run
            Tth1_past = Tth1
            Tth2_past = Tth2

        post_now = 0

        blink( powerIn_state + 1 ) #1 or 2

except KeyboardInterrupt:
    print "Program terminated by user..."

#except Exception as e:
#    print e
#    logme(e, logfile_error)
#    if emailing: sendreport(email_recipient, 'General exception on thermo_control.py', e)
#
#    print e,

finally:
    print "Claning GPIO's state..."
    GPIO.cleanup()
    if emailing: sendreport(email_recipient, 'Solar Heater Control ending', 'Solar Heater Control ending')
    logme( datetime.now().strftime(fmt) + ' | Solar Heater Control ending',  logfile_info)



