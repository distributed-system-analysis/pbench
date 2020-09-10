# Getting Started

The following is an introduction on how to use the pbench agent.

Pbench can be used to either automate tool execution and postprocessing for
you, or also run any of its built-in benchmark scripts.  This first test will
run the fio benchmark.

## Installation

If you have not done so, install `pbench-agent` (via RPM or other Linux
distribution supported method, documented in `INSTALL` file).

After `pbench-agent` is installed, verify that your path includes:

```
/opt/pbench-agent:/opt/pbench-agent/util-scripts:/opt/pbench-agent/bench-scripts
```

If you do not have this, you may need to source your `.bashrc`, re-log in, or
just run, `. /opt/pbench-agent/profile` to have the path updated.


## Tool Registration

After you are certain the path is updated, register the default set of tools:

```
register-tool-set
```

This command will register the default tool set, which consists of `sar`,
`mpstat`, `iostat`, `pidstat`, `proc-vmstat`, `proc-interrupts`, and `perf`.

When registering these tools, `pbench-agent` checks if they are installed and
may install some of them if they are not present.  Some of these tools are
built from source, so you may see output from fetching the source and
compiling.  Following any installation, you should have this output:

```
sar tool is now registered in group default
[debug]tool_opts: default --interval="3"
[debug]checking to see if tool is installed...
iostat is installed
iostat tool is now registered in group default
[debug]tool_opts: default --interval="3"
[debug]checking to see if tool is installed...
mpstat is installed
mpstat tool is now registered in group default
[debug]tool_opts: default --interval="3"
[debug]checking to see if tool is installed...
pidstat is installed
pidstat tool is now registered in group default
[debug]tool_opts: default --interval="3"
[debug]checking to see if tool is installed...
proc-vmstat tool is now registered in group default
[debug]tool_opts: default --interval="3"
[debug]checking to see if tool is installed...
proc-interrupts tool is now registered in group default
[debug]tool_opts: default --record-opts="record -a --freq=100"
[debug]checking to see if tool is installed...
perf tool is now registered in group default
```

If at any time you are unsure which tools are registered, you can run:

```
# list-tools
default: perf,proc-interrupts,proc-vmstat,pidstat,mpstat,iostat,sar
```

The output above shows which tools are in the "default" tool group.  And by
specifying the `--with-options` switch, you get the options used for these
tools:

```
# list-tools --with-options
default: perf --record-opts="record -a --freq=100",proc-interrupts --interval="3",
proc-vmstat --interval="3",pidstat --interval="3",mpstat --interval="3",iostat --interval="3",sar --interval="3"
```

In the above example, the `--interval` option is set for all tools but `perf`.
Optioonally, you can change these individually with the register-tool command:

```
# register-tool --name=pidstat -- --interval=10
[debug]tool_opts: --interval="10"
[debug]checking to see if tool is installed...
pidstat is installed
pidstat tool is now registered in group default
```

Then run `list-tools --with-options` again to confirm:

```
# list-tools --with-options
default: pidstat --interval="10",perf --record-opts="record -a --freq=100",
proc-interrupts --interval="3",proc-vmstat --interval="3",mpstat --interval="3",iostat --interval="3",sar --interval="3"
```

And the interval for `pidstat` is now `10`.


## Running a Benchmark

OK, now that the tools are registered, it's time the run the benchmark. We'll
use the `fio` benchmark for this exmaple. To run, simply type 'pbench_fio',
the wrapper script `pbench-agent` provides for the `fio` benchmark.

If this is the first time running `fio` via the `pbench-agent`, `pbench-agent`
will attempt to download and compile `fio`.  You may see quite a bit of output
from this.  Once `fio` is installed, `pbench-agent` will run several tests by
default.  Output for each will look something like this:

```
about to run fio read with 4 block size on /tmp/fio
--------fio will use this job file:--------
[global]
bs=4k
ioengine=libaio
iodepth=32
direct=1
time_based=1
runtime=30
[job1]
rw=read
filename=/tmp/fio
size=896M
-------------------------------------------
```

Right before the `pbench_fio` script starts a `fio` job, it will call
`start-tools`, which will produce output like this:

```
[debug][start-tools]/opt/pbench-agent/tool-scripts/sar --start --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][start-tools]/opt/pbench-agent/tool-scripts/iostat --start --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][start-tools]/opt/pbench-agent/tool-scripts/mpstat --start --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][start-tools]/opt/pbench-agent/tool-scripts/pidstat --start --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][start-tools]/opt/pbench-agent/tool-scripts/proc-vmstat --start --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][start-tools]/opt/pbench-agent/tool-scripts/proc-interrupts --start --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][start-tools]/opt/pbench-agent/tool-scripts/perf --start --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --record-opts="record -a --freq=100"
```

That is output from `start-tools` starting all of the tools that were
registered.

Next is the output from the actual `fio` job:

```
fio: Going to run [/usr/local/bin/fio /var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/fio.job]
job1: (g=0): rw=read, bs=4K-4K/4K-4K/4K-4K, ioengine=libaio, iodepth=32
fio-2.1.7
Starting 1 process
job1: Laying out IO file(s) (1 file(s) / 896MB)

job1: (groupid=0, jobs=1): err= 0: pid=12961: Thu Sep 11 12:55:47 2014
  read : io=1967.4MB, bw=67147KB/s, iops=16786, runt= 30003msec
    slat (usec): min=3, max=77, avg= 7.95, stdev= 2.45
    clat (msec): min=1, max=192, avg= 1.90, stdev= 1.48
     lat (msec): min=1, max=192, avg= 1.90, stdev= 1.48
    clat percentiles (usec):
     |  1.00th=[ 1736],  5.00th=[ 1736], 10.00th=[ 1752], 20.00th=[ 1752],
     | 30.00th=[ 1768], 40.00th=[ 1768], 50.00th=[ 1768], 60.00th=[ 1912],
     | 70.00th=[ 1912], 80.00th=[ 2064], 90.00th=[ 2096], 95.00th=[ 2224],
     | 99.00th=[ 2256], 99.50th=[ 2256], 99.90th=[10304], 99.95th=[10816],
     | 99.99th=[44800]
    bw (KB  /s): min=34373, max=70176, per=100.00%, avg=67211.32, stdev=5212.44
    lat (msec) : 2=78.09%, 4=21.73%, 10=0.05%, 20=0.10%, 50=0.01%
    lat (msec) : 100=0.01%, 250=0.01%
  cpu          : usr=5.97%, sys=22.23%, ctx=501089, majf=0, minf=332
  IO depths    : 1=0.1%, 2=0.1%, 4=0.1%, 8=0.1%, 16=0.1%, 32=100.0%, >=64=0.0%
     submit    : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.0%, 64=0.0%, >=64=0.0%
     complete  : 0=0.0%, 4=100.0%, 8=0.0%, 16=0.0%, 32=0.1%, 64=0.0%, >=64=0.0%
     issued    : total=r=503651/w=0/d=0, short=r=0/w=0/d=0
     latency   : target=0, window=0, percentile=100.00%, depth=32

Run status group 0 (all jobs):
   READ: io=1967.4MB, aggrb=67146KB/s, minb=67146KB/s, maxb=67146KB/s, mint=30003msec, maxt=30003msec

Disk stats (read/write):
    dm-1: ios=501328/154, merge=0/0, ticks=947625/12780, in_queue=960429, util=99.53%, aggrios=503626/101, aggrmerge=25/55, aggrticks=949096/9541, aggrin_queue=958491, aggrutil=99.49%
  sda: ios=503626/101, merge=25/55, ticks=949096/9541, in_queue=958491, util=99.49%
```

Now that this `fio` job is complete, the `pbench_fio` script calls `stop-tools`:

```
[debug][stop-tools]/opt/pbench-agent/tool-scripts/sar --stop --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][stop-tools]/opt/pbench-agent/tool-scripts/iostat --stop --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]stopping sar
[debug][stop-tools]/opt/pbench-agent/tool-scripts/mpstat --stop --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]stopping iostat
[debug][stop-tools]/opt/pbench-agent/tool-scripts/pidstat --stop --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]stopping mpstat
[debug][stop-tools]/opt/pbench-agent/tool-scripts/proc-vmstat --stop --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]stopping pidstat
[debug][stop-tools]/opt/pbench-agent/tool-scripts/proc-interrupts --stop --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]stopping proc-vmstat
[debug][stop-tools]/opt/pbench-agent/tool-scripts/perf --stop --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --record-opts="record -a --freq=100"
[debug]stopping proc-interrupts
waiting for PID 12934 (perf) to finish
```

Next, `pbench_fio` calls `postprocess-tools`. This is what generates the
`.csv` files and renders the `.html` file containing the NVD3 graphs for the
tool data.

```
collecting /proc
collecting /sys
[debug][postprocess-tools]/opt/pbench-agent/tool-scripts/sar --postprocess --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][postprocess-tools]/opt/pbench-agent/tool-scripts/iostat --postprocess --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug][postprocess-tools]/opt/pbench-agent/tool-scripts/mpstat --postprocess --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]postprocessing iostat
[debug][postprocess-tools]/opt/pbench-agent/tool-scripts/pidstat --postprocess --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]postprocessing mpstat
[debug][postprocess-tools]/opt/pbench-agent/tool-scripts/proc-vmstat --postprocess --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]postprocessing pidstat
[debug][postprocess-tools]/opt/pbench-agent/tool-scripts/proc-interrupts --postprocess --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --interval="3"
[debug]postprocessing proc-vmstat
[debug][postprocess-tools]/opt/pbench-agent/tool-scripts/perf --postprocess --iteration=1-read-4KiB --group=default --dir=/var/lib/pbench/fio__2014-09-11_12:54:42/1-read-4KiB/tools-default default --record-opts="record -a --freq=100"
[debug]postprocessing proc-interrupts
```

This will repeat for a total of 6 different `fio` jobs, then the `fio`
benchmark will be complete.  Now that the job is complete, we want to move
the results to the archive host.  The results are currently in
/var/lib/pbench/fio-<date>.  To move these results, simply run:

```
# move-results
```

Once that command completes, the data should be moved to the configured
archive host.  To view your results, use a link like this in your browser
(replacing the "resultshost.example.com" with your pbench deployed web server,
and replacing the "your-HOSTNAME" with the $(hostname -s) of the machine where
you issued the "move-results" above):

   http://resultshost.example.com/results/<your-HOSTNAME>/?C=M;O=D

Towards the top of the list, there should be a directory like
"`fio__2014-09-11_12:54:42`".  That is your pbench `fio` job.  Click on that
directory to see the results.

There should be a file, `fio-summary.txt`, which will contain the results for
all of the `fio` jobs that were run.

In this same directory, there should be more sub-directories, one for each
`fio` job.  They should have a format like "`N-[read|write]-MKiB`".  In
pbench-speak, these are called an "iteration" and usually start with
"1-". Under each of these you will find the details of that job/iteration:

 * `fio.cmd`:       the actual `fio` command used
 * `fio.job`:       the job file `pbench_fio` created
 * `result.txt`:    the output from the `fio` job
 * `tool-default`:  all of the collected tool data
 * `sysinfo`:       data `pbench_fio` collected from `/sys` & `/proc`

Under the `tools-default` directory, there should be text output for each tool
as well as `.html` files, and a `csv` sub-directory containing all of the raw
tool data.
