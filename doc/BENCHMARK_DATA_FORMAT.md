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

## Benchmark Metrics: Throughput, Latency, Resource, and Efficiency

The four remaining entris in a bechmark iteration represent the benchmark output.  These
are called metric classes.  The two primary metric classes are throughput (work over time)
and latency (time to complete work).  The final two classes, resource and efficiency, are
not always used, and usually require the collection of other data from the benchmark (or a
tool).  The resource metric class is recording of some kind of system or host resource, like
disk utilization or busy cpu cycles.  The efificency metric is a ratio of some throughput
metric divided by some resource metric, like "gigabits-per-second per processor-core".  If
this is used, it is almost always a derivation of two other metrics in the result.json.

### Benchmark-defined Metrics (Metric Types)

Within the metric classes are metric types.  A metric type is a specific kind of metric.
For example, a metric type of "received-packets-per-second", or "transmitted-packets-per-second"
would be defined in the metric class of throughput.
A benchmark may define any metric type, as long as it represents the metric class
appropriately (for example, "packet-per-second" a throughput metric and "packet-round-trip-time"
a latency metric).

There can be multiple instances of the same metric type.  The only requirement is that the
instances have enough meta-data to uniquely identify them from other instances of the same
matric type.

For example, a metric type for the Uperf benchmark, "Gbps" could be defined the following way:

result.json:
<pre>
[
  {"iteration_data": {
    "parameters": { },
    "throughput": {
      "Gb_sec": [
        {
          "client_hostname": "10.10.20.189",
          "closest sample": 1,
          "description": "Number of gigabits sent by client for a period of 1 second",
          "mean": 0.2502,
          "role": "client",
          "server_hostname": "10.10.20.81",
          "server_port": "20010",
          "stddev": 0.005392,
          "stddevpct": 2.155,
          "uid": "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%",
          "samples":
            [
              {
                "timeseries":
                  [
                    {"date": 1532427464295, "value": 0.257708371628372},
                    {"date": 1532427465296, "value": 0.256177998001998}
                  ]
                "value": 0.249042502073812
              },
              {
                 "timeseries":
                  [
                    {"date": 1532427464295, "value": 0.257708371628372},
                    {"date": 1532427465296, "value": 0.256177998001998}
                  ]
                "value": 0.258456676332289
              }
            ]
  }
   "iteration_number": <integer>,
   "iteration_name": <string>
  },
  { <another-iteration> },
  { <another-iteration> }
]
</pre>

In the above example, there is one instance of the metric-type, "Gb_sec".  The minimum fields required [for both pbench reporting and for data import to ElasticSearch] for an instance are:

1. role: This is just a overall term for the role of this metric, as it realtes to the benchmark component that generated it.  For exmaple, in Uperf, this metric came from the client process, so the role is "client".  There is no restriction on what the value can be as long as it is alpha-numeric.

2. mean [, stddev, stdevstddevpct, and closest-sample]: This is the actual metric value.  It is called the mean because pbench supports the concept of running the same test mulitple times, collecting multiple samples of the result, and then computing a "mean" [and standard deviation].  Note that it is not required that the netive benchmark handle the execution of multiple test samples (pbench can do this for you), and the user can even request that only one test sample is taken.  However, in order to have a consistent format for storing data, the "mean", "stddev", and "stddevpct" is always used, regardless of the number of test samples executed.  Note: if your benchmark script is using the built-in script, "process-iteration-samples", then that script will calculate and populate these values for you.  See further details in the built-in benhcmark processing scripts section.

3. description: This is the definition of the metric type, like, "Number of gigabits sent by client for a period of 1 second".  This should be as descriptive as possible without exceeding one sentance.  The description is probably not adequate if it does not provide more information that the name of the metric-type.  For exmaple, the description for the metric type, "Gb_sec", should not simply be, "Gigabits per second".

4. uid: This describes the format of the UID.  Pbench then uses this format to construct the UID for an instance of the metric type, and this is how mulitple instances of the same metric type are uniquely identified.  Note that the fields described in uid are also required.  For example, if uid is defnied as "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%", this metric type must also provide definitions for "client_hostname", "server_hostname", and "server_port".  The selection of these fileds in uid are at the discretion of the benchmark script author, but they must be chosen such that multiple instances do not have the same values for all of the these fields referenced.  Extra care should be used to identify all of the charateristics of a metric instance.

The section, "samples", describes the metric data from mutliple samples of test execution.  If there are not mutiple test execution samples, then mean, stddev, stdevstddevpct must be populated.  If there are multiple test samples, then this samples filed must be populated.  At a minimum, the "value" field must be defined, and optionally the timeseries can also be used.


## Aggreation of Metrics


