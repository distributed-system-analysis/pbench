# Benchmark Data Format

The following documents how data from a benchmark execution is organized in pbench.

A challenge we have in pbench is to take information from any of the benchmarks and organize it in such a way that pbench can process this data in a common way.  This can be difficult because individual benchmarks are not written with goal of providing data in the exact same format.  However, with pbench, we want to use common code to process and present benchmark data to the user.  We also want to provide this data to other projects which go beyond
what pbench does (httpd) for reporting.  Therefore, the need arises to find a common format for benchmark execution data.

## What Is Benchmark Data?

Benchmark data is really any information associated with an execution of that benchmark.  Most think of the output or result,
but the options you use to execute the benchmark are equally important.  For example, uperf may report gigabits-per-second, while fio may report IOPS (and dozens of other metrics).  Uperf may use the option, "--test-type=stream" while fio uses "--rw=randrw".  All of this information is critical to reference when it comes to reviewing a result or comparing more than one result.

There are also metrics which may not be present in the native benchmark, but pbench provides through its features.  For example, pbench may run the exact same test multiple times in order to produce a mean and standard deviation.  Pbench may also coordinate several concurrent benchmark executions (for example, many containers running the same fio test at the same time) and provide an aggregate result.  These types of metrics also need to be considered when designing a common model for benchmark data.

### Benchmark Data Types

When a benchmark is executed, the data we have falls in to two categories: Parameters and Metrics

Parameters describe how the benchmark was executed.  It includes the native benchmark arguments, as well as arguments from the
pbench-benchmark script.  These pbench parameters are things like:
<pre>
--samples
--clients
--servers
--max-stddev-pct
--max-iteration-failures
</pre>
Native benchmark parameters are arguments that are from the benchmark binary.  For example fio includes (but not limited to)
<pre>
--rw
--bs
--ioengine
--iodepth
</pre>

### A Collection of Benchmark Data

A pbench-benchmark script usually facilitates the ability to run several combinations of benchmark parameters, resulting in several different ways that the benchmark is executed.  For example, with pbench-fio, one might use --rw=randread,randwrite and --bs=4k,64k.  The pbench-benchmark script for fio will run fio four different ways:
<pre>
--rw=randread --bs=4k
--rw=randread --bs=64k
--rw=randwrite --bs=4k
--rw=randwrite --bs=64k
</pre>
Each of these ways the benchmark is run is called a benchmark-iteration.  When pbench stores the benchmark data, the data for each benchmark iteration is an element in a json array, stored in result.json

result.json:
<pre>
[ {iteration1}, {iteration2}... {iterationN} ]
</pre>
Each iteration element includes three items, iteration_data, iteration_number, and iteration_name.  Iteration_data includes the bulk of the benchmark data, while iteration_number and iteration_name are just used to aid reporting in pbench web server.  Therefore, the above json expands to include:

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

Of these five, all but parameters include data that comes from either the benchmark output, tool output, or both.  "Parameters" documents the options used to run this benchmark-iteration: both the native bencmark options (like rw=write) and the pbench options (--samples=5).

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
The "benchmark" array is here as a placeholder, should pbench-benchmark script later allow the execution of more than one type of benchmark (like fio and uperf) within the same benchmark-iteration.  This is not the case today.

At a minimum, these parameters must exist: benchmark_name, benchmark_version, max_stddevpct, primary_metric, and uid.  Additonally, any native-benchmark parameter that is required to execute that benchmark must also exist here.  For example, "test-type" is required for uperf and "rw" is required for fio.  Ideally, every single benchmark paremeter that is known should be documented here, even if they are not provided by the user when calling the pbench-benchmark script.  For example, if a user does not specify --ioengine for fio, but fio uses ioengine=sync by default, it should be documented here.

## Metric-Classes: Throughput, Latency, Resource, and Efficiency

The four remaining entries in a bechmark iteration represent the benchmark output.  These are called metric-classes.  The two primary metric-classes are throughput (work over time) and latency (time to complete work).  The final two classes, resource and efficiency, are not always used, and usually require the collection of other data from the benchmark (or a tool).  The resource metric class is recording of some kind of system or host resource, like disk utilization or busy cpu cycles.  The efificency metric is a ratio of some throughput metric divided by some resource metric, like "gigabits-per-second per processor-core".  If this is used, it is almost always a derivation of two other metrics in the result.json.

## Benchmark-defined Metrics (Metric-Types)

Within the metric-classes are metric-types.  A metric-type is a specific kind of that metric-class.  For example, a metric-type of "received-packets-per-second", or "transmitted-packets-per-second" would be defined in the metric-class of throughput.  Another example could be "file-create-time" and fall under the latency metric-class.  A benchmark may define any metric type, as long as it represents the metric class appropriately.  Below is an example, Gb_sec:

result.json:
<pre>
[
  {"iteration_data": {
    "parameters": { },
    "throughput": {
      "Gb_sec": [
        {
          "client_hostname": "10.10.20.189",
          "description": "Number of gigabits sent by client for a period of 1 second",
          "mean": 0.2502,
          "server_hostname": "10.10.20.81",
          "server_port": "20010",
          "uid": "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%",
  }
   "iteration_number": <integer>,
   "iteration_name": <string>
  },
  { <another-iteration> },
  { <another-iteration> }
]
</pre>

When defining the metric-type, the following fields must be included:

1. mean: This is the actual metric value (in this case how many gigabits per second).  It is called the mean because pbench supports the concept of running the same test mulitple times (documented below), collecting multiple samples of the result, and then computing a "mean" [and standard deviation].  If your result includes multiple samples, "mean" can be omitted, and the pbench processing will generste this for you.

2. description: This is the definition of the metric-type, like, "Number of gigabits sent by client for a period of 1 second".  This should be as descriptive as possible without exceeding one sentance.

3. uid: This describes the format of the metric-type UID.  This instructs Pbench how to assemble the UID from the other fields provided by substituting any string with %<string>% with the value of a field with amatching name.  For exmaple, if you were to have:
  
<pre>
{
  "client_hostname" : "saturn"
  "uid": "client_hostname:%client_hostname%
}
</pre>

Pbench can construct a uid for this metric-type as, "client_hostname:saturn".  This should be self evident, but for clarity:  any fields described in uid (like client in the above example) are also required.

Optionally the following fields may also be defined:

1. samples: This is an array of multiple values for this metric-type, one for each benchmark execution.  The multiple executions (samples) of the benchmark should be run in the exact same way.  Each element in the array can have one of two field types:

<pre>
"samples":
            [
              {
                "timeseries":
                  [
                    {"date": 1532427464295, "value": 0.257708371628372},
                    {"date": 1532427465296, "value": 0.256177998001998}
                  ]
              },
              {
                 "timeseries":
                  [
                    {"date": 1532427464295, "value": 0.257708371628372},
                    {"date": 1532427465296, "value": 0.256177998001998}
                  ]
              }
            ]
</pre>

In the example above, the timeseries field is assigned an array of records composed of a timestamp and a value.  This is used when a benchmark provides a series of values over time, like a periodic output of gigabits-per-second.  When this is provided, pbench will compute a average of the timeseries data for you and add to the document once processed:

<pre>
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
</pre>

If the timeseries data is not provided, then the "value" field is required:

<pre>
"samples":
            [
              {
                "value": 0.249042502073812
              },
              {
                "value": 0.258456676332289
              }
            ]
</pre>

When there is a presence of multuple samples, pbench processing will use this information to populate the "mean", "maxsdtdev", and "maxsdtdevpct" fields for you.  After processing, it would look like:

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

### Multiple Instances of the Same Metric-Type

For some benchmarks there may be only one instance of a particular metric-type.  For example, if you have a benchmark which measures how quickly a container platform can start new containers, you might have a metric like "containers_started_per_second", and this is all the informaiton you are interested in, so you have a single instance of that metric.  However, let's say the benchmark is enhanced to start containers on multiple clusters at the same time.  Now you may be interested in the number of containers started per second on each of the clusters.  Now we would require multiple instances of the same metric-type.  

For example, here are multiple instacnes of the Gb_sec metric-type, as provided by the benchmark for processing by pbench:

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
                "value": 1.1
              },
              {
                "value": 1.1
              }
            ]
          },
          {
          "client_hostname": "10.10.20.190",
          "closest sample": 1,
          "description": "Number of gigabits sent by client for a period of 1 second",
          "mean": 2.1,
          "role": "client",
          "server_hostname": "10.10.20.82",
          "server_port": "20010",
          "stddev": 0,
          "stddevpct": 0,
          "uid": "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%",
          "samples":
            [
              {
                "value": 2.1
              },
              {
                "value": 2.1
              }
            ]
          }
  }
   "iteration_number": <integer>,
   "iteration_name": <string>
  },
  { <another-iteration> },
  { <another-iteration> }
]
</pre>

## Aggreation of Metrics

During processing, pbench will attempt to aggrgate multiple instances of the same metric-type, provided the benchmark did not already define one of the instances with the "role" field assigned to "aggregate".  When creating the new [aggregeate] instance of this metric type, the field for "mean" will represent the sum for all of the instances for a throughput metric-class, and an average for a latency metric-class.  If "samples" are present in the instances, those values will first be aggregated (either by summation or average), then the "mean", "stddev", and "stddevpct" field values will be calculated.  Finally, pbench will copy from the other instances all other field names, and these fields will be assigned a value of "all":

<pre>
[
  {"iteration_data": {
    "parameters": { },
    "throughput": {
      "Gb_sec": [
        {
          "client_hostname": "all",
          "closest sample": 1,
          "description": "Number of gigabits sent by client for a period of 1 second",
          "mean": 3.2,
          "role": "aggregate",
          "server_hostname": "all",
          "server_port": "all",
          "stddev": 0,
          "stddevpct": 0,
          "uid": "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%",
          "samples":
            [
              {
                "value": 3.2
              },
              {
                "value": 3.2
              }
            ]
        },
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
                "value": 1.1
              },
              {
                "value": 1.1
              }
            ]
        },
        {
          "client_hostname": "10.10.20.190",
          "closest sample": 1,
          "description": "Number of gigabits sent by client for a period of 1 second",
          "mean": 2.1,
          "role": "client",
          "server_hostname": "10.10.20.82",
          "server_port": "20010",
          "stddev": 0,
          "stddevpct": 0,
          "uid": "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%",
          "samples":
            [
              {
                "value": 2.1
              },
              {
                "value": 2.1
              }
            ]
        }
  }
   "iteration_number": <integer>,
   "iteration_name": <string>
  },
  { <another-iteration> },
  { <another-iteration> }
]
</pre>

## Pbench Utilities to Process Benchmark Data

## Example Benchmark: dd

Here we will take a benchmark which is not in pbench and create a result.json.  In this example, we will use dd:

<pre>
# dd if=/dev/zero of=/tmp/myfile bs=4k oflag=sync count=100000
100000+0 records in
100000+0 records out
409600000 bytes (410 MB) copied, 6.76498 s, 60.5 MB/s
</pre>

In this case, we only ran dd once, and so we only have one benchmark iteration and 1 benhcmark sample.  So, there will be just one element in the JSON array:

<pre>
[
  {
   "iteration_data": {},
   "iteration_number": 1,
   "iteration_name": "my-test-dd"
  },
]
</pre>

From the command, we can see that five parameters are used: if, of, bs, oflag, and count.  We also need the benchmark version, so we'll run:

<pre>
# dd --version
dd (coreutils) 8.22
</pre>

Now we have enough information to populate the parameters section:

<pre>
[
  {
    "parameters":
      {
        "benchmark":
          [
            {
              "benchmark_name": "dd",
              "benchmark_version": "8.22",
              "if": "/dev/zero",
              "of": "/tmp/myfile",
              "bs": "4k",
              "oflag": "sync",
              "count" : "100000"
            }
          ]
      }
</pre>

Now we need to create the metrics for this iteration.  From the output, we have two possible metrics:

<pre>
409600000 bytes (410 MB) copied, 6.76498 s, 60.5 MB/s
</pre>

One is the throughput metric (work over time), megabytes per second, 60.5.  The other is a latency metric (elapsed time to complete an item of work), the number of seconds complete the dd command, 6.76498.  Now some may not be quite that interested in the total time, but it could be an interesting metric to some, so we will keep it.  However, we will make the megabytes per second the primary metric.  Let's first update the parameters section for that:

<pre>
            {
              "benchmark_name": "dd",
              "benchmark_version": "8.22",
              "primary_metric": "MB_sec",
              "if": "/dev/zero",
              "of": "/tmp/myfile",
              "bs": "4k",
              "oflag": "sync",
              "count" : "100000"
            }
</pre>

Now let's create a metric-type and an instance of the metric type for megabytes per second.  At the very leat, we need a description and a uid.  At this point, since we only have one "dd" running at one time, and we don't have multiple instances of the MB_sec metric-type, there's really no point to use a UID with unique fields -as there can be only one instance of the metric anyway.  However, if you were to write a script which laucnhed many concurrent copies of dd, then the UID would be necessary.  The UID could include information like where data was read from, or where data was written to.  However, for now, we will skip this:

<pre>
{
    "parameters": {}
    "throughput": 
      {
        "MB_sec":
          [
            {
              "description": "The average number of megabytes copied in a period of 1 second",
              "uid": "",
              "mean": 60.5,
            }
          ]
      }
      
And that's all we need for this metric.  For the latency metric, we'll add:

{
    "parameters": {}
    "throughput": {}
    "latency":
      {
        "elapsed_time_sec":
          [
            {
              "description": "The total elapsed time in seconds to complete the dd command",
              "uid": "",
              "mean": 6.76498,
            }
          ]
      }
      
And that's all there is to it!  The complete JSON doc would look like:

<pre>
[
  {
    "iteration_data":
      {
        "parameters":
          {
            "benchmark":
              [
                {
                  "benchmark_name": "dd",
                  "benchmark_version": "8.22",
                  "if": "/dev/zero",
                  "of": "/tmp/myfile",
                  "bs": "4k",
                  "oflag": "sync",
                  "count" : "100000"
                }
              ]
          },
        "throughput": 
          {
            "MB_sec":
              [
                {
                  "description": "The average number of megabytes copied in a period of 1 second",
                  "uid": "",
                  "mean": 60.5,
                }
              ]
          },
        "latency":
          {
            "elapsed_time_sec":
              [
                {
                  "description": "The total elapsed time in seconds to complete the dd command",
                  "uid": "",
                  "mean": 6.76498,
                }
              ]
          }      
      },
    "iteration_number": 1,
    "iteration_name": "my-first-dd-test"
  }
]  
</pre>


## Example Benchmark: fio
