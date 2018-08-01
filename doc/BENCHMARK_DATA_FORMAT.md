# Benchmark Data Format

The following documents how data from a benchmark execution is organized in pbench.

A challenge we have in pbench is to take informaton from any of the
benchmarks and organize it in such a way that pbench can process and
report this data in a common way.  This can be difficult because
individual benchmarks are not written with goal of providing data
in the exact same format.  However, with pebnch, we want to use use
common code to process and present benchmark data to the user.  We
also want to provide this data to other projects which go beyond
what pbench does (httpd) for reporting.  Therefore, the need arises
to find a common format for benchmark execution data.

## What Is Benchmark Data?

Benchmark data is really any information associated with an
execution of that benchmark.  Most think of the output or result,
but the options you use to execute the benchmark are equally important.
For example, uperf may report bits-per-second, while fio may report
iops (and dozens of other metrics).  Uperf may use the option,
"--test-type=stream" while fio uses "--rw=randrw".  All of this
information is critical to reference when it comes to reviewing
a result or comparing more than one result.

There are also metrics which may not be present in the native
benchmark, but pbench provides through its features.  For example,
pbench may run the exact same test multiple times in order to
produce a standard deviation, a metric some benchmarks may
not be able to do.  Pbench may also coordinate several concurrent
benchmark executions (for example, many containers running the same
fio test at the same time) and provide an aggregate result.  These
types of metrics also need to be considerd when designing a
common model for benchmark data.

### Benchmark Data Types

When a benchmark is executed, the data we have falls in to two
categories: Parameters and Metrics

Parameters describe how the benchmark was executed.  It includes
the native benchmark arguments, as well as arguments from the
pbench-benchmark script.  These pbench parameters are things like:
<pre>
--samples
--clients
--servers
--max-stddev-pct
--max-iteration-failures
</pre>
Native benchmark parameters are arguments that are from the benchmark
binary.  For example fio includes (but not limited to)
<pre>
--rw
--bs
--ioengine
--iodepth
</pre>

### A Collection of Benchmark Data

A pbench-benchmark script usually facilitates the ability to run several
combinations of benchmark parameters, resulting in several different ways
that the benchmark is executed.  For example, with pbench-fio, one might
use --rw=randread,randwrite and --bs=4k,64k.  The pbench-benchmark script
for fio will run fio four different ways:
<pre>
--rw=randread --bs=4k
--rw=randread --bs=64k
--rw=randwrite --bs=4k
--rw=randwrite --bs=64k
</pre>
Each of these ways the benchmark is run is called a benchmark-iteration.
When pbench stores the benchmark data, the data for each benchmark
iteration is an element in a json array, stored in result.json

result.json:
<pre>
[ {iteration1}, {iteration2}... {iterationN} ]
</pre>
Each iteration element includes three items, iteration_data, iteration_number,
and iteration_name.  Iteration_data includes the bulk of the benchmark data,
while iteration_number and iteration_name are just used for reporting
in pbench web server.  Therefore, the above json expands to include:

result.json:
<pre>
[
  {
   "iteration_data": {},
   "iteration_number": <integer>,
   "iteration_name": <string>
  },
  { <another-iteration> },
  { <another-iteration> }
]
</pre>

## How Pbench Organizes a Benchmark Iteration

The JSON for interation_data has the following [upper-level] layout:

<pre>
  "parameters" : []
  "throughput" : []
  "latency"    : []
  "resource"   : []
  "efficiency" : []
</pre>  

Of these five, all but parameters include data that comes from either the
benchmark output, tool output, or both.  "Parameters" documents the
options used to run this benchmark-iteration: both the native bencmark
options (like rw=write) and the pbench options (--samples=5).

Currently, "parameters" has two levels of heirarchy:
<pre>
"parameters": {
  "benchmark": [
    {
      "benchmark_name": "uperf",
      "benchmark_version": "1.0.4",
      "clients": "10.10.20.189",
      "instances": 1,
      "max_stddevpct": 10
    }
  ]
}
</pre>
The "benchmark" array is here as a placeholder, should pbench-benchmark script
later allow the execution of more than one type of benchmark (like fio and uperf)
within the same benchmark-iteration.  This is not the case today.

At a minimum, these parameters must exist: benchmark_name, benchmark_version,
max_stddevpct, primary_metric, and uid.  Additonally, any native-benchmark
parameter that is required to execute that benchmark must also exist here.
For example, "test-type" is required for uperf and "rw" is required for fio.
Ideally, every single benchmark paremeter that is known should be documented here,
even if they are not provided by the user when calling the pbench-benchmark
script.  For example, if a user does not specify --ioengine for fio, but fio uses
ioengine=sync by default, it should be documented here.
