# Man pages

---

### pbench-clear-results

---

**NAME**  
pbench-clear-results, Clears the result directory

**SYNOPSIS**  
`pbench-clear-results [-C][--help]`

**DESCRIPTION**  
This command clears the results directory from /var/lib/pbench-agent directory

**OPTIONS**  
 -C, --config PATH  
Path to a pbench-agent configuration file (defaults to the '\_PBENCH_AGENT_CONFIG' environment variable, if defined) [required]

--help  
Show this message and exit.

---

### pbench-clear-tools

---

**NAME**  
pbench-clear-tools, Clear registered tools by name or group

**SYNOPSIS**  
`pbench-clear-tools [-C][-n][-g][-r][--help]
`

**DESCRIPTION**  
Clear all tools which are registered and can filter by name of the group

**OPTIONS**  
-C, --config PATH  
Path to a pbench-agent configuration file (defaults to the '\_PBENCH_AGENT_CONFIG' environment variable, if defined) [required]

-n, --name,--names STR  
Clear only the <tool-name> tool.

-g, --group,--groups STR  
Clear the tools in the <group-name> group. If no group is specified, the 'default' group is assumed.

-r, --remote, --remotes STR  
Clear the tool(s) only on the specified remote(s). Multiple remotes may be specified as a comma-separated list. If no remote is specified, all remotes are cleared

--help  
Show this message and exit.

---

### pbench-copy-results

---

**NAME**  
pbench-copy-results, Copies result tarball to the server

**SYNOPSIS**  
`pbench-copy-results [--help] --user=<user> [--controller=<controller>] [--prefix=<path>][--xz-single-threaded] [--show-server]
`

**DESCRIPTION**  
It keeps the copy of tarball on the pbench-agent and pushes the other to pbench-server

**OPTIONS**  
--user  
This option value is required if not provided by the
'PBENCH_USER' environment variable; otherwise, the value provided
on the command line will override any value provided by the
environment.

--controller  
This option may be used to override the value
provided by the 'PBENCH_CONTROLLER' environment variable; if
neither value is available, the result of 'hostname -f' is used.
(If no value is available, the command will exit with an error.)

--prefix  
This option allows the user to specify an optional
directory-path hierarchy to be used when displaying the result
tar balls on the pbench server.

--show-server  
This will not move any results, but resolve and
then display the pbench server destination for results.

--xz-single-threaded  
This will force the use of a single
thread for locally compressing the result tar balls.

--help  
Show this message and exit.

---

### pbench-list-tools

---

**NAME**  
pbench-list-tools, List all the registered tools with group, host, and remote info.

**SYNOPSIS**  
`pbench-list-tools [-C][-n][-g][-o][--help]
`

**DESCRIPTION**  
List all tools that are registered and can filter by name of the group

**OPTIONS**  
 -C, --config PATH  
Path to a pbench-agent configuration file (defaults to the '\_PBENCH_AGENT_CONFIG' environment variable, if defined) [required]

-n, --name STR  
list the tool groups in which <tool-name> is used.

-g, --group STR  
list the tools used in this <group-name>

-o, --with-option  
list the options with each tool

--help  
Show this message and exit.

---

### pbench-list-triggers

---

**NAME**  
pbench-list-triggers, Lists the registered triggers by group

**SYNOPSIS**  
`pbench-list-triggers[-C][-g][--help]
`

**DESCRIPTION**  
This command will list all the registered triggers by group-name

**OPTIONS**  
 -C, --config PATH  
Path to a pbench-agent configuration file (defaults to the '\_PBENCH_AGENT_CONFIG' environment variable, if defined) [required]

-g, --group,--groups STR  
List all the triggers registered in the <group-name> group.

--help  
Show this message and exit.

---

### pbench-move-result

---

**NAME**  
pbench-move-results, Move all results to pbench-server

**SYNOPSIS**  
`pbench-move-results [--help] [--user=<user>] [--controller=<controller>] [--prefix=<path>] [--xz-single-threaded] [--show-server]
`

**DESCRIPTION**  
Move result directories to the configured pbench-server. Once the tarball is moved successfully, it clears the local copy of the tarball in the pbench-agent.This command is used when result tarball is pushed via SSH

**OPTIONS**  
--user  
This option value is required if not provided by the
'PBENCH_USER' environment variable; otherwise, the value provided
on the command line will override any value provided by the
environment.

--controller  
This option may be used to override the value
provided by the 'PBENCH_CONTROLLER' environment variable; if
neither value is available, the result of 'hostname -f' is used.
(If no value is available, the command will exit with an error.)

--prefix  
This option allows the user to specify an optional
directory-path hierarchy to be used when displaying the result
tar balls on the pbench server.

--show-server  
This will not move any results, but resolve and
then display the pbench server destination for results.

--xz-single-threaded  
This will force the use of a single
thread for locally compressing the result tar balls.

--help  
Show this message and exit.

---

### pbench-register-tool

---

**NAME**  
pbench-register-tool, Registers the specified tools

**SYNOPSIS**  
`pbench-register-tool --name=<tool-name> [--group=<group-name>] [--no-install] [--persistent] [--transient] [--remotes=<remote-host>[,<remote-host>]] [--labels=<label>[,<label>]] -- [all tool specific options here][--help]`

`pbench-register-tool --name=<tool-name> [--group=<group-name>] [--no-install] [--persistent] [--transient] [--remotes=@<remotes-file>] -- [all tool specific options here]`

**DESCRIPTION**  
Register the tools that are specified

**OPTIONS**  
--name

List of available tools:

###### Transient
- 	blktrace
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

##### Persistent
- node-exporter
- dcgm
- pcp

For a list of tool-specific options, run:
/opt/pbench-agent/tool-scripts/<tool-name> --help

[--persistent] [--transient]  
This can be used to specify tool run type.

--remotes  
Single remote host, a list of remote hosts (comma-separated, no spaces) or an "at" sign ("@") followed by a filename. In this last case, the file should contain a list of hosts and their (optional) labels. Each line of the file should contain a hostname, optionally followed by a label separated by a comma (","); empty lines are ignored, and comments are denoted by a leading hash, or pound ("#"), character.

--help  
Show this message and exit.

---

### pbench-register-tool-set

---

**NAME**  
pbench-register-tool-set, Register the specified toolset

**SYNOPSIS**  
`pbench-register-tool-set [--toolset=<tool-set>] [--group=<group-name>] [--interval=<interval>] [--no-install] [--remotes=<remote-host>[,<remote-host>]] [--labels=<label>[,<label>]] [<tool-set>]`

`pbench-register-tool-set [--toolset=<tool-set>] [--group=<group-name>] [--interval=<interval>] [--no-install] [--remotes=@<remotes-file>] [<tool-set>]`

**DESCRIPTION**  
Register all the tools in the specified toolset.

**OPTIONS**  
 --toolset  
Available tool sets from /opt/pbench-agent/config/pbench-agent.cfg:

- heavy
- legacy
- light
- medium

--remotes  
Single remote host, a list of remote hosts (comma-separated, no spaces) or an "at" sign ("@") followed by a filename. In this last case, the file should contain a list of hosts and their (optional) labels. Each line of the file should contain a hostname, optionally followed by a label separated by a comma (","); empty lines are ignored, and comments are denoted by a leading hash, or pound ("#"), character.

--labels  
Where the list of labels must match the list of remotes.

--help  
Show this message and exit.

---

### pbench-register-tool-trigger

---

**NAME**  
pbench-register-tool-trigger, Registers the tool trigger

**SYNOPSIS**  
`pbench-register-tool-trigger[-C][-g][--start-trigger][--stop-trigger][--help]`

**DESCRIPTION**  
Registers tool with the given group and start and stop tool trigger text

**OPTIONS**  
 -C, --config PATH  
Path to a pbench-agent configuration file (defaults to the '\_PBENCH_AGENT_CONFIG' environment variable, if defined) [required]

-g, --group,--groups STR  
Registers the trigger in the <group-name> group. If no group is specified, the 'default'

--start-trigger STR  
[required]

--stop-trigger STR  
[required]

--help  
Show this message and exit.

---

### pbench-results-move

---

**NAME**  
pbench-results-move, Move results tarball to the server

**SYNOPSIS**  
`pbench-results-move[-C][--controller][--token][--delete][--xz-single-threaded][--show-server][--help]
`

**DESCRIPTION**  
Move result directories to the configured Pbench server.This command is used when pushing result tarball using token.

**OPTIONS**  
 -C, --config PATH  
Path to a pbench-agent configuration file (defaults to the '\_PBENCH_AGENT_CONFIG' environment variable,if defined) [required]

--controller STR  
Override the default controller name

--token STR  
pbench server authentication token [required]

--delete / --no-delete  
Remove local data after successful copy [default: delete]

--xz-single-threaded  
Use single-threaded compression with 'xz'

--show-server STR  
Display information about the pbench server where the result(s) will be moved (Not implemented)

--help  
Show this message and exit.

---

### pbench-user-benchmark

---

**NAME**  
pbench-user-benchmark, Control start/stop/post-process-tools.

**SYNOPSIS**  
`pbench-user-benchmark[-C][--tool-group][--iteration-list][--sysinfo][--pbench-pre][--pbench-post][--use-tool-triggers][--no-stderr-capture]-- <script to run>`

**DESCRIPTION**  
Collects data from the tools registered. Here are the steps involved

- Invoking pbench-user-benchmark with your workload generator as an argument: that will start the collection tools on all the hosts
- Next, it will run your workload generator; when that finishes, it will stop the collection tools on all the hosts
- Finally, the postprocessing phase will gather the data from all the remote hosts and run the postprocessing tools on everything.

**OPTIONS**  
-C, --config PATH  
Path to a pbench-agent configuration file (defaults to the '\_PBENCH_AGENT_CONFIG' environment variable,if defined) [required]

--tool-group  
The tool group to use for the list of tools

--iteration-list  
A file containing a list of iterations to run for the provided script;
the file should contain one iteration per line, with a leading '#' (hash) character used for comments, blank lines are ignored; each iteration line should use alpha-numeric characters before the first space to name the iteration, with the rest of the line provided as arguments to the script;  
_NOTE: --iteration-list is not compatible with --use-tool-triggers_

--sysinfo STR,[STR]  
comma-separated values of system information to be collected; available: default, none, all, ara, block, insights, kernel_config, libvirt, security_mitigations, sos, stockpile, topology

--pbench-pre STR  
Path to the script which will be executed before tools are started  
_NOTE: --pbench-pre is not compatible with --use-tool-triggers_

--pbench-post STR  
Path to the script which will be executed after tools are stopped and postprocessing is complete  
_NOTE: --pbench-post is not compatible with --use-tool-triggers_

--use-tool-triggers  
Use tool triggers instead of normal start/stop around script;  
_NOTE: --use-tool-triggers is not compatible with --iteration-list,--pbench-pre, or --pbench-post_

--no-stderr-capture  
Do not capture the stderr of the script to the result.txt file

--help  
Show this message and exit.
