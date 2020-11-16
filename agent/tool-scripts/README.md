# Tool Scripts (`agent/tool-scripts`)

The scripts in this directory represent the pbench-agent "tools" that users
can register to collect data from the systems related to a workload.  Each
tool available for use with a `pbench-register-tool --name=<tool>` CLI
invocation is listed in the `meta.json` file as either "transient" or
"persistent".

The Tool Meister running on each host where tools are registered is
responsible for invoking that tool script to collect its generated data.  The
commands to start and stop tools are sent to each Tool Meister at the
appropriate time via the `pbench-init/start/stop/end/send/postprocess-tools`
CLI interfaces.

The tool scripts in this directory provide the interfaces used by the Tool
Meister for checking for prerequisites, starting the tool data capture
("datalog" scripts), stopping the tool data capture, and optionally
post-processing the captured tool data ("postprocess" scripts).

Most of the pbench-agent "tools" are symlinks to one script named `base-tool`.
This allows us to share all the common behaviors between the tools, while
handling differences where appropriate.

The `external-data-source`, `node-exporter`, and `dcgm` "tools" are handled
separately since they operate a bit differently from the rest.  See below for
more details.

## The Tool Life Cycle

There are 4 phases that the Tool Meister sub-system offers. The first phase is
for executing all the "persistent" tools.  Once the Tool Meister sub-system is
up and running, this phase is started first (required), and is ended before
the Tool Meister sub-system is shut down (required).  The `pbench-init-tools`
CLI interface begins the "persistent" tools phase, and the `pbench-end-tools`
CLI interface closes out the phase.  More about "persistent" tools below.

The second phase is for executing all the "transient" tools (described below).
This phase must be started after the "persistent" tools phase begins, and must
end before the "persistent" tools phase ends.  However, the phase can be
repeated as many times as the caller likes.  The `pbench-start-tools` CLI
begins the phase by starting all the "transient" tools.  Then the caller must
invoke the `pbench-stop-tools` CLI to shut down all the "transient" tools,
ending this phase.

The third phase is for all transient tools to send their data back to the host
driving all the local and remote Tool Meisters.  This phase can happen after
all "transient" tool phases have executed, but must occur before ending the
"persistent" tools phase.  The execution of the `pbench-send-tools` CLI
interface encapsulates this phase.

The fourth, and final, phase is the post-processing for "transient" tool data.
All the post-processing for a given "transient" tool phase is invoked locally
on the host driving all the Tool Meisters.  The execution of the
`pbench-postprocess-tools` CLI interface handles this phase for a given
"transient" tool phase, and must be invoked after the `pbench-send-tools` for
a given phase.

Inspecting the `agent/bench-scripts` directory for how the various scripts
invoke the aforementioned CLIs will give you a sense of how these phases are
used.

## Examples of the Four Phases

The standard way tools are invoked:

```
  $ pbench-init-tools
  $ pbench-start-tools
  $ pbench-stop-tools
  $ pbench-send-tools
  $ pbench-postprocess-tools
  $ pbench-end-tools
```

A benchmark might require multiple transient tool phases:

```
  $ pbench-init-tools
  $
  $ pbench-start-tools
  $ pbench-stop-tools
  $ pbench-send-tools
  $ pbench-postprocess-tools
  $
  $ pbench-start-tools
  $ pbench-stop-tools
  $ pbench-send-tools
  $ pbench-postprocess-tools
  $
  $ pbench-end-tools
```

Another benchmark environment might need to delay sending data and
post-processing at a later time:

```
  $ pbench-init-tools
  $
  $ pbench-start-tools
  $ pbench-stop-tools
  $
  $ pbench-start-tools
  $ pbench-stop-tools
  $
  $ # All workloads done, its safe to send data remotely
  $
  $ pbench-send-tools
  $ pbench-send-tools
  $
  $ pbench-end-tools
  $
  $ # All data has been collected, run all the post-processing locally.
  $
  $ pbench-postprocess-tools
  $ pbench-postprocess-tools
```

## Persistent Tools

A "persistent" tool is one where the tool data capture does not happen
locally, but is continuously sent remotely.  These tools are started via the
call to `pbench-init-tools`, and end when the `pbench-end-tools` is invoked.
All persistent tools do not have a separate "datalog" or "postprocessing"
script, and are paired with a collection agent provided by the tool, run by
the Tool Data Sink.

There are two persistent tools available today, `node-exporter` and `dcgm`.
Both "tools" are Prometheus-based data exporters, where the Tool Data Sink
directs a local instance of Prometheus to pull the data from each host with
those tools registered.

### The `node-exporter` and `dcgm` Tools

The `node-exporter` and `dcgm` tool scripts provided in this directory are
placeholders only in order for users to see them alongside the other tools.
The actual implementation of these tools is handled by the Tool Meister code
directly.

## Transient Tools

A "transient" tool is one where the tool data capture happens on the host
local to where the tool is running.  All transient tools store their data
locally as directed by their invoking Tool Meister.  For Tool Meisters running
on the same host where the caller is driving the benchmark (where
`pbench-tool-meister-start` was invoked), the captured data is stored directly
into the local `${benchmark_result_dir}` directory.  Tool Meisters running on
hosts remote from the driving benchmark host direct the tools to store their
data in a temporary directory tracked by the Tool Meister.

Each remote Tool Meister is responsible for gathering up the captured data for
each tool and sending it back to the Tool Data Sink on the host driving the
benchmark.

The classic example of a "transient" tool is "perf record", where that command
captures its data in a local directory, and has no interface in the tool
itself to send it remotely.

### The `external-data-source` Tool

The `external-data-source` tool provides a way for recording the URL to a data
source external to the benchmark environment.  For example, the benchmark
environment might be using a third-party data collection tool which has its
own web interface to review data.  This tool gives the user a way to record
the URL associated with the benchmark.

This tool does not provide any `datalog` or `postprocess` scripts, and no
command to collect data is invoked.

## The `datalog` and `postprocess` Directories for "transient" Tools

For each transient tool, there must be a `datalog` script which is responsible
for invoking the command that generates the data for that tool.  These scripts
are stored in the `datalog` sub-directory named `<tool>-datalog`.

Each transient tool can optionally provide a "stop-postprocess" script which
handles the required steps for properly capturing all of the relevant data and
meta-data for that tool.  These scripts are stored in the "postprocess"
sub-directory named `<tool>-stop-postprocess`.  The `stop-postprocess` script
is executed on the host running the tool, after that tool is stopped
successfully, but before reporting back to the caller that the tool has stopped.

Similarly, each transient tool can also optionally provide a "postprocess"
script which handles post-processing steps for the captured data to apply any
required or desired transformations.  The script is executed on the local host
when the `pbench-postprocess-tools` script is invoked.

## Installation Steps for the `node-exporter` Tool

In cases where your operating system distribution does not provide a package
for installing the Prometheus `node_exporter` command, consider following the
steps below on the hosts from which you want to collect Prometheus
`node_exporter` data, and/or refer to the `node_exporter` [GitHub source
repository](https://github.com/prometheus/node_exporter).

 1. `wget https://github.com/prometheus/node_exporter/releases/download/v1.0.1/node_exporter-1.0.1.linux-amd64.tar.gz`  (latest version, change version number as desired)
 1. `tar xvfz node_exporter-*.*-amd64.tar.gz`
 1. `mv node_exporter-1.0.1.linux-amd64 node_exporter`  (not necessary but nice)
 1. Test that it's working:

    1. `cd node_exporter`
    1. `./node_exporter`  (should see a list of default collectors accessible through port 9100)

Once installed on a particular host, register the `node-exporter` tool with
pbench for that host: `pbench-register-tool --name=node-exporter
--remote=host.example.com -- --inst=/path/to/node_exporter_dir`.

## Installation Steps for the `dcgm` Tool

The `dcgm` tool refers to Nvidia's Data Center GPU Manager software which
provides a prometheus data exporter, `dcgm_prometheus.py`.  You can find the
installation instructions for setting up DCGM at
https://docs.nvidia.com/datacenter/dcgm/latest/dcgm-user-guide/getting-started.html#installation.

Determine the path prefix where the `samples/scripts/dcgm_prometheus.py` file
exists in the installation, that is: `ls -ld
${dcgm_path}/samples/scripts/dcgm_prometheus.py` should work to list the
`dcgm_prometheus.py` file.

Once installed on a particular host, register the `dcgm` tool with pbench for
that host using the path prefix determined above: `pbench-register-tool
--name=dcgm --remote=host.example.com -- --inst=${path_prefix}`.
