# Man pages
 
**Contents**

## Performance tool management commands
-  [pbench-clear-results](#pbench-clear-results)
-  [pbench-clear-tools](#pbench-clear-tools)
-  [pbench-list-tools](#pbench-list-tools)
-  [pbench-list-triggers](#pbench-list-triggers)
-  [pbench-register-tool](#pbench-register-tool)
-  [pbench-register-tool-set](#pbench-register-tool-set)
-  [pbench-register-tool-trigger](#pbench-register-tool-trigger)
## Benchmark commands
-  [pbench-user-benchmark](#pbench-user-benchmark)
## Upload to Pbench Server
### Pbench Server 0.69
- [pbench-move-result](#pbench-move-result)
- [pbench-copy-results](#pbench-copy-results) 
### Pbench Server 1.0
-  [pbench-results-move](pbench-results-move)


---

#### pbench-clear-results

---

**NAME**  
`pbench-clear-results`, Clears the result directory

**SYNOPSIS**  
`pbench-clear-results [OPTIONS]`

**DESCRIPTION**  
This command clears the results directory from `/var/lib/pbench-agent` directory

**OPTIONS**  
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.


`--help`  
Show this message and exit.

---

#### pbench-clear-tools

---

**NAME**  
`pbench-clear-tools`, Clear registered tools by name or group

**SYNOPSIS**  
`pbench-clear-tools [OPTIONS]`

**DESCRIPTION**  
Clear all tools which are registered and can filter by name of the group

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

#### pbench-copy-results

---

**NAME**  
`pbench-copy-results`, Copies result tarball to the 0.69 Pbench Server.

**SYNOPSIS**  
`pbench-copy-results [--help] --user=<user> [--controller=<controller>] [--prefix=<path>][--xz-single-threaded] [--show-server]`

**DESCRIPTION**  
Push the benchmark result to the Pbench Server without removing it from the local host. This command requires `/opt/pbench-agent/id_rsa` file with the private SSH key,when pushing to a 0.69 Pbench Server.

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
This will not move any results, but resolve and
then display the pbench server destination for results.

`--xz-single-threaded`  
This will force the use of a single
thread for locally compressing the result tar balls.

`--help`  
Show this message and exit.


---

#### pbench-list-tools

---

**NAME**  
`pbench-list-tools`, List all the registered tools with group, host, and remote info.

**SYNOPSIS**  
`pbench-list-tools [OPTIONS]`

**DESCRIPTION**  
List all tools that are registered and can filter by name of the group

**OPTIONS**  
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`-n`, `--name` STR  
list the tool groups in which <`STR`> is used.

`-g`, `--group` STR  
list the tools used in this <`STR`>

`-o`, `--with-option`  
list the options with each tool

`--help`  
Show this message and exit.

---

#### pbench-list-triggers

---

**NAME**  
`pbench-list-triggers`, Lists the registered triggers by group

**SYNOPSIS**  
`pbench-list-triggers[-C][-g][--help]`

**DESCRIPTION**  
This command will list all the registered triggers by `group-name`

**OPTIONS**  
 `-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`-g`, `--group`, `--groups` STR  
List all the triggers registered in the <`STR`> group.

`--help`  
Show this message and exit.

---

#### pbench-move-result

---

**NAME**  
`pbench-move-results`, Move all results to 0.69 Pbench Server.

**SYNOPSIS**  
`pbench-move-results [--help] [--user=<user>] [--controller=<controller>] [--prefix=<path>] [--xz-single-threaded] [--show-server]`

**DESCRIPTION**  
This command can only be used for a 0.69 Pbench Server destination, and requires a `/opt/pbench-agent/id_rsa` file with the private SSH key of the server's pbench account.

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
This will not move any results, but resolve and
then display the pbench server destination for results.

`--xz-single-threaded`  
This will force the use of a single
thread for locally compressing the result tar balls.

`--help`  
Show this message and exit.

---

#### pbench-register-tool

---

**NAME**  
`pbench-register-tool`, Registers the specified tools

**SYNOPSIS**  
`pbench-register-tool --name=<tool-name> [--group=<group-name>] [--no-install] [--persistent | --transient] [--remotes=<remote-host>[,<remote-host>]] [--labels=<label>[,<label>]] -- <tool-specific-options> [--help]`

`pbench-register-tool --name=<tool-name> [--group=<group-name>] [--no-install] [--persistent | --transient] [--remotes=@<remotes-file>] -- <tool-specific-options>`

**DESCRIPTION**  
Register the tools that are specified .
List of available tools:

**Transient**
- blktrace
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

**OPTIONS**  
`--name` STR
This can be used register a specific tool by name.
For a list of tool-specific options, run:
/opt/pbench-agent/tool-scripts/<`tool-name`> --help

`[--persistent | --transient]`  
This can be used to specify tool run type.

`--remotes`  
Single remote host, a list of remote hosts (comma-separated, no spaces) or an "at" sign (`@`) followed by a filename. In this last case, the file should contain a list of hosts and their (optional) labels. Each line of the file should contain a hostname, optionally followed by a label separated by a comma (`,`); empty lines are ignored, and comments are denoted by a leading hash, or pound (`#`), character.

`--help`  
Show this message and exit.

---

#### pbench-register-tool-set

---

**NAME**  
`pbench-register-tool-set`, Register the specified toolset

**SYNOPSIS**  
`pbench-register-tool-set [--toolset=<tool-set>] [--group=<group-name>] [--interval=<interval>] [--no-install] [--remotes=<remote-host>[,<remote-host>]] [--labels=<label>[,<label>]] [<tool-set>]`

`pbench-register-tool-set [--toolset=<tool-set>] [--group=<group-name>] [--interval=<interval>] [--no-install] [--remotes=@<remotes-file>] [<tool-set>]`

**DESCRIPTION**  
Register all the tools in the specified toolset.

**OPTIONS**  
 `--toolset`  
Available tool sets from /opt/pbench-agent/config/pbench-agent.cfg:

- heavy
- legacy
- light
- medium

`--remotes`  
Single remote host, a list of remote hosts (comma-separated, no spaces) or an "at" sign (`@`) followed by a filename. In this last case, the file should contain a list of hosts and their (optional) labels. Each line of the file should contain a hostname, optionally followed by a label separated by a comma (`,`); empty lines are ignored, and comments are denoted by a leading hash, or pound (`#`), character.

`--labels`  
Where the list of labels must match the list of remotes.

`--help`  
Show this message and exit.

---

#### pbench-register-tool-trigger

---

**NAME**  
`pbench-register-tool-trigger`, Registers the tool trigger

**SYNOPSIS**  
`pbench-register-tool-trigger [OPTIONS]`

**DESCRIPTION**  
Registers tool with the given group and start and stop tool trigger text

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

#### pbench-results-move

---

**NAME**  
`pbench-results-move`, Move results tarball to the server to a 1.0 Pbench Server.

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
pbench server authentication token [required]

`--delete` | `--no-delete`  
Remove local data after successful copy [default: delete]

`--xz-single-threaded`  
Use single-threaded compression with `xz`

`--show-server` STR  
Display information about the pbench server where the result(s) will be moved (Not implemented)

`--help`  
Show this message and exit.

---

#### pbench-user-benchmark

---

**NAME**  
`pbench-user-benchmark`, Control start/stop/post-process-tools.

**SYNOPSIS**  
`pbench-user-benchmark[-C][--tool-group][--iteration-list][--sysinfo][--pbench-pre][--pbench-post][--use-tool-triggers][--no-stderr-capture] -- <command-to-run>`

**DESCRIPTION**  

Collects data from the registered tools while running a user-specified action. This can be a specific synthetic benchmark workload, a real workload, or simply a delay to measure system activity.

Here are the steps involved

- Invoking `pbench-user-benchmark` with your workload generator as an argument: that will start the collection tools on all the hosts
- Next, it will run your workload generator; when that finishes, it will stop the collection tools on all the hosts
- Finally, the postprocessing phase will gather the data from all the remote hosts and generates `result.txt` file by running the postprocessing tools on everything 

`<command-to-run>`
A script, executable, or shell command to run while gathering tool data. Use `--`
to stop processing of `pbench-user-benchmark` options if your command includes
options, like `pbench-user-benchmark --config string -- fio --bs 16k`.

**OPTIONS**  
`-C`, `--config` PATH  
Path to the Pbench Agent configuration file.
This option is required if not provided by the `_PBENCH_AGENT_CONFIG` environment variable.

`--tool-group` STR
The tool group to use for the list of tools

`--iteration-list` STR  
A file containing a list of iterations to run for the provided script;
the file should contain one iteration per line. With a leading `#` (hash) character used for comments and blank lines are ignored.
Each iteration line should use alpha-numeric characters before the first space to name the iteration, with the rest of the line provided as arguments to the script;  
_NOTE: --iteration-list is not compatible with --use-tool-triggers_

`--sysinfo` STR[,STR...]  
comma-separated values of system information to be collected; available: `default` `none` `all` `ara` `block` `insights` `kernel_config` `libvirt` `security_mitigations` `sos` `stockpile` `topology`

`--pbench-pre` STR  
Path to the script which will be executed before tools are started  
_NOTE: --pbench-pre is not compatible with --use-tool-triggers_

`--pbench-post` STR  
Path to the script which will be executed after tools are stopped and postprocessing is complete  
_NOTE: --pbench-post is not compatible with --use-tool-triggers_

`--use-tool-triggers`  
Use tool triggers instead of normal start/stop around script;  
_NOTE: --use-tool-triggers is not compatible with --iteration-list,--pbench-pre, or --pbench-post_

`--no-stderr-capture`  
Do not capture the  standard error output of the script to the `result.txt` file

`--help`  
Show this message and exit.
