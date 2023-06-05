# Man pages
 
## Commands by functional group

### Performance tool management commands
-  [pbench-clear-results](#pbench-clear-results)
-  [pbench-clear-tools](#pbench-clear-tools)
-  [pbench-list-tools](#pbench-list-tools)
-  [pbench-list-triggers](#pbench-list-triggers)
-  [pbench-register-tool](#pbench-register-tool)
-  [pbench-register-tool-set](#pbench-register-tool-set)
-  [pbench-register-tool-trigger](#pbench-register-tool-trigger)
### Benchmark commands
-  [pbench-user-benchmark](#pbench-user-benchmark)
### Upload to Pbench Server
#### Pbench Server 0.69
- [pbench-move-results](#pbench-move-results)
- [pbench-copy-results](#pbench-copy-results) 
#### Pbench Server 1.0
-  [pbench-results-move](pbench-results-move)

## Commands

---

### pbench-clear-results

---

**NAME**  
`pbench-clear-results` - clears the result directory

**SYNOPSIS**  
`pbench-clear-results [OPTIONS]`

**DESCRIPTION**  
This command clears the results directory from `/var/lib/pbench-agent` directory.

**OPTIONS**  
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.


`--help`  
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
`-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`-n`, `--name`, `--names` STR  
Clear only the <`STR`> tool.

`-g`, `--group`, `--groups` STR  
Clear the tools in the <`STR`> group. If no group is specified, the `default` group is assumed.

`-r`, `--remote`, `--remotes` STR  
Clear the tool(s) only on the specified remote(s). Multiple remotes may be specified as a comma-separated list. If no remote is specified, all remotes are cleared

`--help`  
Show this message and exit.

---

### pbench-copy-results

---

**NAME**  
`pbench-copy-results` - copy result tarball to the 0.69 Pbench Server

**SYNOPSIS**  
`pbench-copy-results [--help] --user=<user> [--controller=<controller>] [--prefix=<path>][--xz-single-threaded] [--show-server]`

**DESCRIPTION**  
Push the benchmark result to the Pbench Server without removing it from the local host. This command requires `/opt/pbench-agent/id_rsa` file with the private SSH key, when pushing to a 0.69 Pbench Server.

**OPTIONS**  
`--user`  
This option value is required if not provided by the
`PBENCH_USER` environment variable; otherwise, a value provided
on the command line will override any value provided by the
environment.

`--controller`  
This option may be used to override the value
provided by the `PBENCH_CONTROLLER` environment variable; if
neither value is available, the result of `hostname -f` is used.
(If no value is available, the command will exit with an error.)

`--prefix`  
This option allows the user to specify an optional
directory-path hierarchy to be used when displaying the result
files on the 0.69 Pbench Server.

`--show-server`  
This will not move any results but will resolve and
then display the pbench server destination for results.

`--xz-single-threaded`  
This will force the use of a single
thread for locally compressing the result tar balls.

`--help`  
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
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`-n`, `--name` STR  
List the tool groups in which tool <`STR`> is registered.

`-g`, `--group` STR  
List all the tools registered in the <`STR`> group.

`-o`, `--with-option`  
List the options with each tool

`--help`  
Show this message and exit.

---

### pbench-list-triggers

---

**NAME**  
`pbench-list-triggers` - lists the registered triggers by group

**SYNOPSIS**  
`pbench-list-triggers[-C][-g][--help]`

**DESCRIPTION**  
This command will list all the registered triggers by `group-name`. 

**OPTIONS**  
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`-g`, `--group`, `--groups` STR  
List all the triggers registered in the <`STR`> group.

`--help`  
Show this message and exit.

---

### pbench-move-results

---

**NAME**  
`pbench-move-results` - move all results to 0.69 Pbench Server

**SYNOPSIS**  
`pbench-move-results [--help] [--user=<user>] [--controller=<controller>] [--prefix=<path>] [--xz-single-threaded] [--show-server]`

**DESCRIPTION**  
Push the benchmark result to the 0.69 Pbench Server , and requires a `/opt/pbench-agent/id_rsa` file with the private SSH key of the server's pbench account.

**OPTIONS**  
`--user`  
This option value is required if not provided by the
`PBENCH_USER` environment variable; otherwise, a value provided
on the command line will override any value provided by the
environment.

`--controller`
This option may be used to override the value
provided by the `PBENCH_CONTROLLER` environment variable; if
neither value is available, the result of `hostname -f` is used.
(If no value is available, the command will exit with an error.)

`--prefix`  
This option allows the user to specify an optional
directory-path hierarchy to be used when displaying the result
tar balls on the pbench server.

`--show-server`  
This will not move any results but will resolve and
then display the pbench server destination for results.

`--xz-single-threaded`  
This will force the use of a single
thread for locally compressing the result tar balls.

`--help`  
Show this message and exit.

---

### pbench-register-tool

---

**NAME**  
`pbench-register-tool` - registers the specified tool

**SYNOPSIS**
`pbench-register-tool --name=<tool-name> [--group=<group-name>] [--no-install] [--persistent | --transient] [--remotes=<remote-host>[,<remote-host>]] [--labels=<label>[,<label>]] [--help] [-- <tool-specific-options>]`

`pbench-register-tool --name=<tool-name> [--group=<group-name>] [--no-install] [--persistent | --transient] [--remotes=@<remotes-file>] [--help] [-- <tool-specific-options>]`

**DESCRIPTION**  
Register the tool that are specified.
List of available tools:

**Transient**
-   blktrace
- 	bpftrace
- 	cpuacct
- 	disk
- 	dm-cache
- 	docker
- 	docker-info
- 	external-data-source
- 	haproxy-ocp
- 	iostat
- 	jmap
- 	jstack
- 	kvm-spinlock
- 	kvmstat
- 	kvmtrace
- 	lockstat
- 	mpstat
- 	numastat
- 	oc
- 	openvswitch
- 	pcp-transient
- 	perf
- 	pidstat
- 	pprof
- 	proc-interrupts
- 	proc-sched_debug
- 	proc-vmstat
- 	prometheus-metrics
- 	qemu-migrate
- 	rabbit
- 	sar
- 	strace
- 	sysfs
- 	systemtap
- 	tcpdump
- 	turbostat
- 	user-tool
- 	virsh-migrate
- 	vmstat

 **Persistent**
- node-exporter
- dcgm
- pcp

For a list of tool-specific options, run:
>`/opt/pbench-agent/tool-scripts/[<tool-name>] --help`

**OPTIONS**  
`--name` STR  
<`STR`> specifies the name of the tool to be registered.


`[--persistent | --transient]`  
This can be used to specify tool run type.

`--remotes`  
Single remote host, a list of remote hosts (comma-separated, no spaces) or an "at" sign (`@`) followed by a filename. In this last case, the file should contain a list of hosts and their (optional) labels. Each line of the file should contain a hostname, optionally followed by a label separated by a comma (`,`); empty lines are ignored, and comments are denoted by a leading hash (`#`), character.

`--help`  
Show this message and exit.

---

### pbench-register-tool-set

---

**NAME**  
`pbench-register-tool-set` - register the specified toolset

**SYNOPSIS**  
`pbench-register-tool-set [--group=<group-name>] [--interval=<interval>] [--no-install] [--remotes=<remote-host>[,<remote-host>]] [--labels=<label>[,<label>]] [--help]`

`pbench-register-tool-set [--group=<group-name>] [--interval=<interval>] [--no-install] [--remotes=@<remotes-file>] [--help]`

**DESCRIPTION**  
Register all the tools in the specified toolset.

**OPTIONS**
`--remotes`  
Single remote host, a list of remote hosts (comma-separated, no spaces) or an "at" sign (`@`) followed by a filename. In this last case, the file should contain a list of hosts and their (optional) labels. Each line of the file should contain a hostname, optionally followed by a label separated by a comma (`,`); empty lines are ignored, and comments are denoted by a leading hash (`#`), character.

`--labels`  
Where the list of labels must match the list of remotes.

`--help`  
Show this message and exit.

---

### pbench-register-tool-trigger

---

**NAME**  
`pbench-register-tool-trigger` - registers the tool trigger

**SYNOPSIS**  
`pbench-register-tool-trigger [OPTIONS]`

**DESCRIPTION**  
Registers tool with the given group and start and stop tool trigger text.

**OPTIONS**  
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`-g`, `--group`, `--groups` STR  
Registers the trigger in the <`STR`> group. If no group is specified, the `default` group is assumed. 

`--start-trigger` STR  
[required]

`--stop-trigger` STR  
[required]

`--help`  
Show this message and exit.

---

### pbench-results-move

---

**NAME**  
`pbench-results-move` - move results tarball to the server to a 1.0 Pbench Server

**SYNOPSIS**  
`pbench-results-move [OPTIONS]`

**DESCRIPTION**  
This command uploads one or more result directories to the configured v1.0 Pbench Server. The specified API Key is used to authenticate the user and to establish ownership of the data on the server. Once the upload is complete, the result directories are, by default, removed from the local system.


**OPTIONS**  
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`--controller` STR  
Override the default controller name

`--token` STR  
Pbench Server API key [required]

`--delete` | `--no-delete`  
Remove local data after successful copy [default: delete]

`--xz-single-threaded`  
Use single-threaded compression with `xz`

`--help`  
Show this message and exit.

---

### pbench-user-benchmark

---

**NAME**  
`pbench-user-benchmark` - run a workload and collect performance data

**SYNOPSIS**  
`pbench-user-benchmark[-C][--tool-group][--iteration-list][--sysinfo][--pbench-pre][--pbench-post][--use-tool-triggers][--no-stderr-capture] -- <command-to-run>`

**DESCRIPTION**  

Collects data from the registered tools while running a user-specified action. This can be a specific synthetic benchmark workload, a real workload, or simply a delay to measure system activity.

Invoking pbench-user-benchmark with a workload generator as an argument will perform the following steps:

- start the collection tools on all the hosts
- execute the workload generator
- stop the collection tools on all the hosts
- gather the data from all the remote hosts and generates a result.txt file by running the tools' post-processing on the collected data

`<command-to-run>`
A script, executable, or shell command to run while gathering tool data. Use `--`
to stop processing of `pbench-user-benchmark` options if your command includes
options, like 
> `pbench-user-benchmark --config string -- fio --bs 16k`

**OPTIONS**  
`-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`--tool-group` STR  
The tool group to use for data collection.

`--iteration-list` STR  
A file containing a list of iterations to run for the provided script;
the file should contain one iteration per line. With a leading hash (`#`) character used for comments and blank lines are ignored.
Each iteration line should use alpha-numeric characters before the first space to name the iteration, with the rest of the line provided as arguments to the script.    
_NOTE: --iteration-list is not compatible with --use-tool-triggers_

`--sysinfo` STR[,STR...]  
comma-separated values of system information to be collected; available: `default`,`none`,`all`,`ara`,`block`,`insights`,`kernel_config`,`libvirt`,`security_mitigations`,`sos`,`stockpile`,`topology`

`--pbench-pre` STR  
Path to the script which will be executed before tools are started.  
_NOTE: --pbench-pre is not compatible with --use-tool-triggers_

`--pbench-post` STR  
Path to the script which will be executed after tools are stopped and postprocessing is complete  
_NOTE: --pbench-post is not compatible with --use-tool-triggers_

`--use-tool-triggers`  
Use tool triggers instead of normal start/stop around script.  
_NOTE: --use-tool-triggers is not compatible with --iteration-list,--pbench-pre, or --pbench-post_

`--no-stderr-capture`  
Do not capture the standard error output of the script in the `result.txt` file

`--help`  
Show this message and exit.
