# Scripts for measuring total wall power and system component power


# Dependencies

Developed with Python3

Control and monitoring of power meters over Ethernet uses pyvisa. To install:
```
  pip install -U pyvisa
```

# Usage

sample\_metrics.py is a framework for running a collection of "samplers"
(i.e. classes called "Sampler" that live in files in the "samplers" directory).
The log file contains values from each of the samplers in CSV format in
the same order as given on the command line (grep for "^CSV, " to extract).

Each sampler must be a class called Sampler, and must have the following
methods:
```
  close(self)
  get_titles(self)
  get_values(self)
```
The first method is called just before deletion.
Second returns a tuple of CSV titles for the first CSV line in the log file.
Third returns a tuple of CSV values for subsequent CSV lines in the log file.

Detailed usage is shown below, note that any number of samplers can
be appended to the command.

```
sample_metrics.py -h
usage: sample_metrics.py [-h] [-I SAMPLING_INTERVAL] [-D SAMPLING_DURATION]
                         [-o OUTFILE] [-l LOGFILE] [-v]
                         sampler_name [sampler_name ...]

positional arguments:
  sampler_name          Python sampler class to instantiate

optional arguments:
  -h, --help            show this help message and exit
  -I SAMPLING_INTERVAL, --sampling_interval SAMPLING_INTERVAL
                        Sampling Interval (sec)
  -D SAMPLING_DURATION, --sampling_duration SAMPLING_DURATION
                        Sampling Duration (sec)
  -o OUTFILE, --outfile OUTFILE
                        Output file
  -l LOGFILE, --logfile LOGFILE
                        Comma Separated Variable result
  -v, --verbose         Increase output verbosity

```

