# boiler-control
Controlling boilers using an arduino thermometer and a pi controller

Runs on a Raspberry pi, connected with a relay to control 2 (sun-boosted) water boilers that are connected in series on the roof of a hotel.
There is a python script (thermo-dev.py) that runs in a loop, to do that...

An Arduino Uno, measures the temperature in the boilers, mainly the last boiler in the chain is relevant.
The Rpi connects to the arduino via http.

Also, an other arduino is connected to 3 ferromagnets to measure the current passing from the 3 phases of the mains power input. This sends data to our Rpi via USB, and there is a "kind of algorithm" to calculate the temperature of the fuses, and if that gets too high, then the system shuts down the boilers so that we dont burn the fuses.

The raspberry runs a webserver to view temperatures, power currents, a graph, and also to control the boilers manually, if we want. Also, in case of the automatic control, we can set the target temperatures there.

There is a script (analysis-auto.py) that prepares a graph (temperature vs time) to present at a webpage. This runs with cron
Also, there is a script, (auto-run-thermo.py) that checks if the main script is running and if it is not, then run it again. This is to ensure that nothing will stop us in the case of exceptions.

Notice: Code is really really, but really ugly. Also, mostly uncommented... Also, I have to discover and upload here the source code that both arduinos run (which is not really long)
