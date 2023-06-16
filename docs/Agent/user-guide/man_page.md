# Man pages

## Commands by functional group

### Performance tool management commands

- [pbench-clear-results](#pbench-clear-results)
- [pbench-clear-tools](#pbench-clear-tools)
- [pbench-list-tools](#pbench-list-tools)
- [pbench-list-triggers](#pbench-list-triggers)
- [pbench-register-tool](#pbench-register-tool)
- [pbench-register-tool-set](#pbench-register-tool-set)
- [pbench-register-tool-trigger](#pbench-register-tool-trigger)

### Benchmark commands

- [pbench-user-benchmark](#pbench-user-benchmark)

### Upload to Pbench Server

#### Pbench Server 0.69

The 0.69 variant of Pbench Server relies on a private `id_rsa` key for the
Pbench Server's `pbench` user in order to upload data to the server using `ssh`
protocols. Results on the server have no ownership, and are visible to
everyone. Results cannot be deleted except by administrators.

- [pbench-move-results](#pbench-move-results)
- [pbench-copy-results](#pbench-copy-results)

#### Pbench Server 1.0

The 1.0 variant of Pbench Server relies on OIDC2 authentication to identify
specific users. Data is uploaded to the server through HTTPS APIs, so that all
results are owned and managed by the individual user. Results can be published
to make them accessible to other users.

- [pbench-results-move](#pbench-results-move)

## Commands

---

### pbench-clear-results

---

**NAME**

`pbench-clear-results` - clears the result directory

**SYNOPSIS**

`pbench-clear-results [OPTIONS]`

**DESCRIPTION**

This command clears the results directories from `/var/lib/pbench-agent` directory.

**OPTIONS**

[`-C`, `--config`] `<path>`\
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`--help`\
Show this message and exit.

---

### pbench-clear-tools

---

**NAME**

`pbench-clear-tools` - clear registered tools by name or group

**SYNOPSIS**

`pbench-clear-tools [OPTIONS]`

**DESCRIPTION**

Clear all tools which are registered and can filter by name of the group.

**OPTIONS**

[`-C`, `--config`] `<path>`\
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

[`-n`, `--name`, `--names`] `<name>`\
Clear only the `<name>` tool.

[`-g`, `--group`, `--groups`] `<group>`\
Clear the tools in the `<group>`. If no group is specified, the `default` group is assumed.

[`-r`, `--remote`, `--remotes`] `<host>[,<host>]...`\
Clear the tool(s) only on the specified remote(s). Multiple remotes may be specified as a comma-separated list. If no remote is specified, all remotes are cleared.

`--help`\
Show this message and exit.

---

### pbench-copy-results

---

**NAME**

`pbench-copy-results` - copy result tarball to a Pbench Server

**SYNOPSIS**

`pbench-copy-results --user=<user> [OPTIONS]`

**DESCRIPTION**

Push all accumulated benchmark results to a Pbench Server without removing
them from the local host.

**OPTIONS**

`--user <user>`\
This option value is required if not provided by the
`PBENCH_USER` environment variable; otherwise, a value provided
on the command line will override any value provided by the
environment.

`--controller <controller>`\
This option may be used to override the value
provided by the `PBENCH_CONTROLLER` environment variable; if
neither value is available, the result of `hostname -f` is used.
(If no value is available, the command will exit with an error.)

`--prefix <prefix>`\
This option allows the user to specify an optional
directory-path hierarchy to be used when displaying the result
files on the Pbench Server.

`--show-server`\
This will not move any results but will resolve and
then display the pbench server destination for results.

`--xz-single-threaded`\
This will force the use of a single
thread for locally compressing the result files.

`--help`\
Show this message and exit.

---

### pbench-list-tools

---

**NAME**

`pbench-list-tools` - list all the registered tools optionally filtered by name or group

**SYNOPSIS**

`pbench-list-tools [OPTIONS]`

**DESCRIPTION**

List tool registrations, optionally filtered by tool name or tool group.

**OPTIONS**

[`-C`, `--config`] `<path>`\
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

[`-n`, `--name`] `<name>`\
List the tool groups in which tool `<name>` is registered.

[`-g`, `--group`] `<group>`\
List all the tools registered in the `<group>`.

`-o`, `--with-option`\
List the options with each tool.

`--help`\
Show this message and exit.

---

### pbench-list-triggers

---

**NAME**

`pbench-list-triggers` - list the registered triggers by group

**SYNOPSIS**

`pbench-list-triggers [OPTIONS]`

**DESCRIPTION**

This command will list all the registered triggers by `group-name`.

**OPTIONS**

[`-C`, `--config`] `<path>`\
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

[`-g`, `--group`, `--groups`] `<group>`\
List all the triggers registered in the `<group>`.

`--help`\
Show this message and exit.

---

### pbench-move-results

---

**NAME**

`pbench-move-results` - move all results to a Pbench Server

**SYNOPSIS**

`pbench-move-results [OPTIONS]`

**DESCRIPTION**

Push all accumulated benchmark results to a Pbench Server. On successful
completion, this command removes the results from the local host.

**OPTIONS**

`--user <user>`\
This option value is required if not provided by the
`PBENCH_USER` environment variable; otherwise, a value provided
on the command line will override any value provided by the
environment.

`--controller <controller>`\
This option may be used to override the value
provided by the `PBENCH_CONTROLLER` environment variable; if
neither value is available, the result of `hostname -f` is used.
(If no value is available, the command will exit with an error.)

`--prefix <prefix>`\
This option allows the user to specify an optional
directory-path hierarchy to be used when displaying the result
tar balls on the pbench server.

`--show-server`\
This will not move any results but will resolve and
then display the pbench server destination for results.

`--xz-single-threaded`\
This will force the use of a single
thread for locally compressing the result files.

`--help`\
Show this message and exit.

---

### pbench-register-tool

---

**NAME**

`pbench-register-tool` - registers the specified tool

**SYNOPSIS**

`pbench-register-tool --name=<tool-name> [OPTIONS] [-- <tool-specific-options>]`

**DESCRIPTION**

Register the specified tool.
List of available tools:

**Transient**

- blktrace
- bpftrace
- cpuacct
- disk
- dm-cache
- docker
- docker-info
- external-data-source
- haproxy-ocp
- iostat
- jmap
- jstack
- kvm-spinlock
- kvmstat
- kvmtrace
- lockstat
- mpstat
- numastat
- oc
- openvswitch
- pcp-transient
- perf
- pidstat
- pprof
- proc-interrupts
- proc-sched_debug
- proc-vmstat
- prometheus-metrics
- qemu-migrate
- rabbit
- sar
- strace
- sysfs
- systemtap
- tcpdump
- turbostat
- user-tool
- virsh-migrate
- vmstat

**Persistent**

- node-exporter
- dcgm
- pcp

For a list of tool-specific options, run:

> `/opt/pbench-agent/tool-scripts/<tool-name> --help`

**OPTIONS**

`--name <tool-name>`\
`<tool-name>` specifies the name of the tool to be registered.

[`-g`, `--group`, `--groups`] `<group>`\
Register the tool in `<group>`. If no group is specified, the `default` group
is assumed.

`[--persistent | --transient]`\
For tools which can be run as either "transient" (where they are started and
stopped on each iteration) or as "persistent" (where they are started before
the first iteration and run continuously over all iterations), these options
determine how the tool will be run.

Most tools can be run only in one mode, so these options are necessary only
when a tool (such as `pcp`) can be run in either mode. Specifying a mode the
tool does not support will produce an error.

`--no-install`\
[To be supplied]

`--labels=<label>[,<label>]...`\
Where the list of labels must match the list of remotes.

`--remotes <host>[,<host>]... | @<file>`\
A single remote host, a list of remote hosts (comma-separated, no spaces) or an
"at" sign (`@`) followed by a filename. In this last case, the file should
contain a list of hosts and their (optional) labels. Each line of the file
should contain a hostname, optionally followed by a label separated by a comma
(`,`); empty lines are ignored, and comments are denoted by a leading hash
(`#`), character.

`--help`\
Show this message and exit.

---

### pbench-register-tool-set

---

**NAME**

`pbench-register-tool-set` - register the specified toolset

**SYNOPSIS**

`pbench-register-tool-set [OPTIONS] <tool-set>`

**DESCRIPTION**

Register all the tools in the specified toolset.

Available `<tool-set>` from /opt/pbench-agent/config/pbench-agent.cfg:

- heavy
- legacy
- light
- medium

**OPTIONS**

`--remotes <host>[,<host>]... | @<file>`\
Single remote host, a list of remote hosts (comma-separated, no spaces) or an
"at" sign (`@`) followed by a filename. In this last case, the file should
contain a list of hosts and their (optional) labels. Each line of the file
should contain a hostname, optionally followed by a label separated by a comma
(`,`); empty lines are ignored, and comments are denoted by a leading hash
(`#`), character.

[`-g`, `--group`] `<group>`\
Register the toolset in `<group>`. If no group is specified, the `default` group is assumed.

`--labels=<label>[,<label>]...`\
Where the list of labels must match the list of remotes. If a remotes file is
specified with `--remotes @<file>` then labels are read from the file instead.

`--interval=<interval>`\
Define a default interval for tools.

`--no-install`\
Don't check whether the expected tools are installed when registering. This can
lead to unexpected errors later, but may also allow running with nonstandard
tool versions if there are no binary incompatibilities.

`--help`\
Show this message and exit.

---

### pbench-register-tool-trigger

---

**NAME**

`pbench-register-tool-trigger` - register the tool trigger

**SYNOPSIS**

`pbench-register-tool-trigger [OPTIONS]`

**DESCRIPTION**

Register triggers which start and stop data collection for the given tool group.

**OPTIONS**

[ `-C`, `--config`] `<path>`\
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG`
environment variable.

[`-g`, `--group`, `--groups`] `<group>`\
Registers the trigger in the `<group>`. If no group is specified, the `default` group is assumed.

`--start-trigger <string>`\
[To be supplied]

`--stop-trigger <string>`\
[To be supplied]

`--help`\
Show this message and exit.

---

### pbench-results-move

---

**NAME**

`pbench-results-move` - move results directories to a Pbench Server

**SYNOPSIS**

`pbench-results-move [OPTIONS]`

**DESCRIPTION**

This command uploads all accumulated results to a Pbench Server.

Two modes are supported:

1. The results are pushed directly to a Pbench Server using the API Key
authentication token specified by `--token` and will be owned by that user.
The Pbench Server URI can be specified with `--server`, or will be defaulted
from the active configuration file.
2. The results are pushed to a Relay server rather than directly to a Pbench
Server, and the command will report the URI of a Relay manifest. The Pbench
Server can later be used to pull the results by supplying the full Relay
manifest URI. The Relay server may be located on any network host accessible
to both the Pbench Agent and the Pbench Server to allow uploading results
through a firewall.

On successful completion, the result directories are removed from the local
system unless `--no-delete` is specified.

**OPTIONS**

[`-C`, `--config`] `<path>`\
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`--relay <relay>`\
Instead of pushing results directly to a Pbench Server, push them to a Relay
server at the specified address. For example, `https://myrelay.example.com`.

`--server <server>`\
Override the default server address in the Pbench Agent configuration file and
push results to the specified Pbench Server address. For example,
`https://pbench.example.com`. This often allows a Pbench Agent to push results
without creating a customized Pbench Agent configuration file.

`--controller <controller>`\
Override the default controller name.

`--token <token>`\
Pbench Server API key [required unless `--relay` is specified].

`--delete` | `--no-delete`\
Remove local data after successful copy [default: `delete`]

`--xz-single-threaded`\
Use single-threaded compression with `xz`.

`--help`\
Show this message and exit.

---

### pbench-user-benchmark

---

**NAME**

`pbench-user-benchmark` - run a workload and collect performance data

**SYNOPSIS**

`pbench-user-benchmark [OPTIONS] <command-to-run>`

**DESCRIPTION**

Collects data from the registered tools while running a user-specified action. This can be a specific synthetic benchmark workload, a real workload, or simply a delay to measure system activity.

Invoking `pbench-user-benchmark` with a workload generator as an argument will perform the following steps:

- Start the collection tools on all the hosts.
- Execute the workload generator.
- Stop the collection tools on all the hosts.
- Gather the data from all the remote hosts and generate a `result.txt` file by running the tools' post-processing on the collected data.

`<command-to-run>`\
A script, executable, or shell command to run while gathering tool data. Use `--`
to stop processing of `pbench-user-benchmark` options if your command includes
options, like

> `pbench-user-benchmark --config string -- fio --bs 16k`

**OPTIONS**

[`-C`, `--config`] `<path>`\
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`--tool-group <tool-group>`\
The tool group to use for data collection.

`--iteration-list <file>`\
A file containing a list of iterations to run for the provided script. The file
must contain one iteration per line. Empty lines are ignored, and comments are
denoted by a leading hash (`#`) character. Each iteration line should use
alpha-numeric characters before the first space to name the iteration, with the
rest of the line provided as arguments to the script.

_NOTE: --iteration-list is not compatible with --use-tool-triggers._

`--sysinfo <module>[,<module>]...`\
Comma-separated values of system information to be collected; available:
`default`, `none`, `all`, `ara`, `block`, `insights`, `kernel_config`,
`libvirt`, `security_mitigations`, `sos`, `stockpile`, `topology`

`--pbench-pre <pre-script>`\
Path to the script which will be executed before tools are started.

_NOTE: --pbench-pre is not compatible with --use-tool-triggers._

`--pbench-post <post-script>`\
Path to the script which will be executed after tools are stopped and
postprocessing is complete.

_NOTE: --pbench-post is not compatible with --use-tool-triggers._

`--use-tool-triggers`\
Use tool triggers instead of normal start/stop sequence when starting and
stopping iterations.

Tool triggers allow starting and stopping tool data collection based on data
in the `<command-to-run>` output stream to allow collecting data over parts
of the execution, dynamically.

_NOTE: --use-tool-triggers is not compatible with --iteration-list,
--pbench-pre, or --pbench-post._

__[TODO: Document the register/list tool trigger commands]__

`--no-stderr-capture`\
Do not capture the standard error output of the script in the `result.txt` file

`--help`\
Show this message and exit.
