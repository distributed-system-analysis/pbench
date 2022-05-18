# Scripts for parsing MLPerf power measurement logs. 


# Dependencies

Developed under Python 3 for Windows.
Other OS enviroments should work.

Latest versions should work, but not actively tested.  The versions below were used for development.

The graphing feature uses plotly.
To install:
```
  pip install dash==1.18.1
  pip install plotly==4.14.1
```

Data handling uses pandas & numpy
To install:
```
  pip install pandas==1.0.5
  pip install numpy==1.19.1
```

Date parsing uses dateutils
To install:
```
  pip install dateutil
```


# Script In-Line Paramters

Inside the parser script are some global variables/options.

The following variables are for modifying the graphing and statistical windows.
```
# g_power_window* : adjusts the time around POWER_BEGIN and POWER_END of the loadgen timestamps to show data in graph.
                    typically used to hide or show setup or settling behavior for further analysis
  g_power_window_before_add_td = timedelta(seconds=0)
  g_power_window_before_sub_td = timedelta(seconds=0)
  g_power_window_after_add_td  = timedelta(seconds=0)
  g_power_window_after_sub_td  = timedelta(seconds=10)
```

# Command-line Parameters

```
  -h, --help            show this help message and exit
  
  -lgi LOADGEN_IN, --loadgen_in LOADGEN_IN
                        Specify directory of loadgen log files to parase from
  -spl SPECPOWER_IN, --specpower_in SPECPOWER_IN
                        Specify PTDaemon power log file (in custom PTD format)
  -pli POWERLOG_IN, --powerlog_in POWERLOG_IN
                        Specify power or data input file (in CSV format)

  -lgo LOADGEN_OUT, --loadgen_out LOADGEN_OUT
                        Specify loadgen CSV output file (default:
                        loadgen_out.csv)
  -plo POWERLOG_OUT, --powerlog_out POWERLOG_OUT
                        Specify power or data CSV output file (default:
                        power_out.csv)

  -g [GRAPH [GRAPH ...]], --graph [GRAPH [GRAPH ...]]
                        Draw/output graphable data over time using the lgi/lgo
                        and pli/plo as input. (Optional) Input a list of
                        strings to filter data
  -s [STATS [STATS ...]], --stats [STATS [STATS ...]]
                        Outputs statistics between loadgen & power/data
                        timestamps using lgi/lgo and pli/plo as inputs.
                        (Optional) Input a list of strings to filter data
  -csv [CSV], --csv [CSV]
                        Outputs statistics to a CSV file (optional parameter,
                        default: stats_out.csv) instead of stdout.
  -w WORKLOAD [WORKLOAD ...], --workload WORKLOAD [WORKLOAD ...]
                        Parse for workloads other than [mobilenet, gnmt,
                        resenet50|resnet, ssd-large|ssdresnet34, or ssd-
                        small|ssdmobilenet]

  -v, --verbose

  -deskew DESKEW, --deskew DESKEW
                        Adjust timing skew between loadgen and power/data logs
                        (in seconds)
```

# Graph/Plots

When using the graph (**-g**) option, the script will loop into server mode.  
Use a browser to connect to http://localhost:8050 (if running on the same system) or to the IP of the system running the script to view the graph(s).

To terminate the server (and script), press Ctrl-C (or equivalent).


# Future plans

- Possible performance enhancements
