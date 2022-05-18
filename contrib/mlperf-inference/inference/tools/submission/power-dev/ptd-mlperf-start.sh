#!/bin/bash
#v0.1 Sample MLperf Inference PTDaemon Start Script

#Edit this option if this script will be executed in a different
#directory than PTDaemon

PTD_PATH="./"

#Name of PTDaemon Executable

PTD_EXECUTABLE=ptd-linux-x86

#Default PTDaemon port 8888

LISTENER_PORT=8888

#Select DEVICE number from PTDaemon help (run ptd-linux-x86 without args)
#Device #8 is Yokogawa WT210
#Device #0 is "Dummy Mode" to simulate an analyzer
@
#Check https://www.spec.org/power/docs/SPECpower-Device_Compatibility.html
#for OS/device/connection compatiblility 

ANALYZER_SELECTION=8

#This is the communication interface your analyzer attaches to
#Example: Serial (/dev/ttySx, USB (/dev/usbtmcx, etc.)

ANALYZER_INTERFACE=/dev/ttyS1

#This option will log to the same directory
#Comment out if you don't want to output a logfile.
LOG_FILE="-l ptd-log.csv"

$PTD_PATH$PTD_EXECUTABLE $LOG_FILE -p $LISTENER_PORT $ANALYZER_SELECTION $ANALYZER_INTERFACE 
