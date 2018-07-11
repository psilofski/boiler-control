#!/bin/bash

#pidof python

STR=$(ps ax | grep -v grep | grep thermo_control.py)

if [ ${#STR} -eq "0" ];
then
#    echo "thermo-dev is not running"
    python /home/pi/thermo-dev/thermo_control.py
fi

