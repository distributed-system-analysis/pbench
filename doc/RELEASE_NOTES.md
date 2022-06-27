This is a very *significant* "minor" release of the pbench-agent code base, primarily to deliver the new "Tool Meister" sub-system.

_*NOTE WELL*_:

 * The notion of a "default" tool set is being deprecated and will be removed in the upcoming Pbench Agent v1.0 release.  To replace it, the Pbench Agent is introducing a few named tool sets.  See "Default Tool Set is _*Deprecated*_; Named tool sets introduced" below.
 * All tools registered prior to installing `v0.71` must be re-registered; tools registered locally, or remotely, on a host with v0.69 or earlier version of the `pbench-agent` will be ignored.  See "Tool registration kept local to the host where registration happens" below.

This release also delivers:

 * Support for RHEL 9 & CentOS Stream 9
 * Support of Prometheus and PCP tool data collection
 * Independence of Pbench Agent "tool" Scripts
 * Removal of gratuitous manipulation of networking firewalls
 * Removal of gratuitous software installation, only checks for requirements
   * True for both tools and benchmark convenience script requirements
   * Change to check command versions instead of RPM versions for `pbench-fio`, `pbench-linpack`, and `pbench-uperf`
 * The `pbench-linpack` benchmark convenience script now provides result graphs, JSON data files, and supports execution on one or more local / remote hosts
 * Required use of `--user` with `pbench-move-results`/`pbench-copy-results`
 * Support for the new HTTP PUT method of posting tar balls
 * Removal of the dependency on the SCL (Software Collections Library)
 * Dropped support for the `pbench-trafficgen` benchmark convenience script
 * Deprecation announcements for unused benchmark convenience scripts:
   * `pbench-run-benchmark`, `pbench-cyclictest`, `pbench-dbench`, `pbench-iozone`, `pbench-migrate`, and `pbench-netperf`
 * Semi-Public CLI Additions, Changes, and Removals
 * Many, many, bug fixes and behavioral improvements

You can review the [**Full ChangeLog**](https://github.com/distributed-system-analysis/pbench/compare/b0.69-bp...v0.71.0) on GitHub (all 560+ commits, tags `b0.69-bp` to `v0.71.0`), or read a summary with relevant details below.

We did not bump the "major" release version number with these changes because we still don't consider all the necessary functionality in place for such a major version bump.

Note that work on the `v0.71` release started in earnest with the `v0.69.3-agent` release (tagged as `b0.69-bp`).  A number of bug fixes and behaviors from the `v0.71` work have already been back-ported and delivered in the various `v0.69.*` releases since then.  These release notes will highlight only the behavioral changes that have not been back-ported previously.

This release supports RHEL 7.9, RHEL 8.6, RHEL 9, CentOS-Stream 8, CentOS-Stream 9 and Fedora 35. For various reasons, it does *NOT* support RHEL 8.x for x < 6 (ansible vs. ansible-core dependency problem), RHEL 9.1 (missing repos) or Fedora 36 (python-3.10 problems). If you need support for any of these, please talk to us: we will do our best to accommodate you in some way, but there is no guarantee.

Installation
====

There are no installation changes in this release: see the [Getting Started Guide](https://distributed-system-analysis.github.io/pbench/gh-pages/start.html) for how to install or update.

After installation or update, you should have version `0.71.0-3g0b7f55850` of the `pbench-agent` RPM installed.

RPMs are available from [Fedora COPR](https://copr.fedorainfracloud.org/coprs/ndokos/pbench/), covering Fedora 35, & 36 (`x86_64` only), EPEL 7, 8, & 9 (`x86_64` and `aarch64`), and CentOS Stream 8 & 9 (`x86_64` and `aarch64`), but please note there are problems with some distros as described above.

There are Ansible [playbooks](https://galaxy.ansible.com/pbench/agent) available via Ansible Galaxy to install the `pbench-agent`, and the pieces needed (key and configuration files) to be able to send results to a Pbench Server.  To use the RPMs provided above via COPR with the playbooks, your inventory file needs to include the `fedoraproject_username` variable set to `ndokos`, for example:

```
...

[servers:vars]
fedoraproject_username = ndokos
pbench_repo_name = pbench-test

...
```

Alternatively, one can specify `fedoraproject_username` on the command line, rather than having it specified in the inventory file:

    ansible-playbook -i <inventory> <playbook> -e '{fedoraproject_username: ndokos}' -e '{pbench_repo_name: pbench-test}'

_**NOTE WELL**_: If the inventory file also has a definition for `pbench_repo_url_prefix` (which was standard practice before `fedoraproject_username` was introduced), it needs to be deleted, otherwise it will override the default repo URL and the `fedoraproject_username` change will not take effect.

While we don't include installation instructions for the new `node-exporter` and `dcgm` tools in the published documentation, you can find a manual installation procedure for the Prometheus "node_exporter" and references to the Nvidia "DCGM" documentation in the [`agent/tool-scripts/README`](https://github.com/distributed-system-analysis/pbench/blob/v0.71.0/agent/tool-scripts/README.md).

Container images built using the above RPMs are available in the [Pbench](https://quay.io/organization/pbench) organization in the Quay.io container image repository using tags `latest`, `v0.71.0`, and `0b7f55850`.


Summary of Changes
====

## Default Tool Set is _*Deprecated*_; Named tool sets introduced

The notion of a "default" tool set is being deprecated and will be removed in the upcoming Pbench Agent v1.0 release.  In preparation for this deprecation, we have added additional named tool sets for users to consider replacing the "default" tool set.

This deprecation announcement is to address the very heavy-weight tools employed by the "default" tool set, including `pidstat`, `proc-interrupts`, and `perf` (aka `perf record`).

The four named tool sets added are:

 * `legacy`:  `iostat`, `mpstat`, `perf`, `pidstat`, `proc-interrupts`, `proc-vmstat`, `sar`, `turbostat` (the current "default" tool set)
 * `light`: `vmstat`
 * `medium`: `${light}`, `iostat`, `sar` (this _will be_ the new default tool set Pbench Agent v1.0)
 * `heavy`: `${medium}`, `perf`, `pidstat`, `proc-interrupts`, `proc-vmstat`, `turbostat`

Users are not required to use the pre-defined tool sets: a user may register whatever tools they like; or, a user may define a custom, named tool set in `/opt/pbench-agent/config/pbench-agent.cfg` (follow the pattern of the default tool set definitions in `/opt/pbench-agent/config/pbench-agent-default.cfg` -- note, we don't support modifications to the default configuration file).

In addition to the "default" tool set deprecation, the `--toolset` option is also deprecated and will be removed with the Pbench Agent v1.0 release.  This is due to the fact that a tool set name will also be required going forward with the v1.0 release.

As a reminder, if you are using the "default" tool set, you need to ensure the `pbench-sysstat`, `perf`, and `kernel-tools` (which provides `turbostat`) RPMs are installed.


## Support for RHEL 9 & CentOS Stream 9

Support for RHEL & CentOS Stream 9 is provided in this release.


## The New "Tool Meister" Sub-System

The "Tool Meister" sub-system (introduced by PR #1248) is the major piece of functionality delivered with the release of `v0.71` of the pbench-agent.

This is a significant change, where the pbench-agent first orchestrates the instantiation of a "Tool Meister" process on all hosts registered with tools, using a Redis instance to coordinate their operation, and the new "Tool Data Sink" process handles the collection of data into the pbench run directory hierarchy.  This effectively eliminates all remote SSH operations for individual tools except the initial one per host to create each Tool Meister instance.

One Tool Meister instance is created per registered host, and then a single Tool Data Sink instance is created on the host where the benchmark convenience script is run.  The Tool Meister instances are responsible for running the registered tools on their respective host, collecting the data generated as appropriate. The Tool Data Sink is responsible for collecting and storing locally all data sent to it from the deployed Tool Meister instances.

### User-Controlled Orchestration of "Tool Meister" Sub-System via Container Images

Container images are provided for the constituent components of the Tool Meister sub-system, the Tool Meister image and the Tool Data Sink image.  The images allow for the orchestration of the Tool Meister sub-system to be handled by the user instead of automatically by the pbench-agent.

### The "Tool Meister" Sub-System with No Tools

While this is not a new feature of the Pbench Agent, it is worth noting that when no tools are registered, the "Tool Meister" sub-system is not deployed and the bench scripts still execute normally.


## Tool registration kept local to the host where registration happens

Along with the new "Tool Meister" sub-system comes a subtle, but significant, change to how tools are registered.

Prior to v0.71, tool registration for remote hosts was recorded locally, _and also_ remotely via ssh.

With v0.71, tools are recorded only locally when they are registered and the validation of remote hosts is deferred until the workload is run. During its initialization, the Tool Meister sub-system now reports when registered tools are not present on registered hosts, and, if a tool is not installed, an error message will be displayed, and the "bench-script" will exit with a failure code.

The registered tools are recorded in a local directory off of the "pbench_run" directory, by default `/var/lib/pbench-agent/tools-v1-<name>`, where `<name>` is the name of the Tool Group under which the tools were registered.

All tools registered prior to installing `v0.71` must be re-registered; tools registered locally or remotely on a host with v0.69 or earlier version of the `pbench-agent` will be ignored.


## New Support for Prometheus and PCP-based Tools

The new "Tool Meister" sub-system enables support of Prometheus and PCP-based tools for data collection.

The existing tools supported prior to the v0.71 release can be categorized as "Transient" tools.  By _transient_ we mean that a given tool is started immediately before and stopped immediately after the execution of a benchmark workload.  For example, when using `pbench-fio -b 4,16,32 -t read,write`, the transient tools are started immediately before each `fio` job is executed, and stopped immediately following its completion, for each of the six `fio` jobs that would be run.

A new category is introduced for Prometheus and PCP called "Persistent" tools. _Persistent_ tools are started once at the beginning of a benchmark convenience script and stopped at its end.  Using the previous `pbench-fio` example, persistent tools would be started before any of the six `pbench-fio` jobs begin and would be stopped once all six end.

When persistent tools are used, data is continuously collected from the data sources ("exporters", in the case of Prometheus, and "PMCDs", in the case of PCP) and stored local to the execution of the Tool Data Sink.

Note that for transient tools, where data for the transient tool is collected locally on the host the tool is registered, the collected data is _usually_ sent to the Tool Data Sink when the benchmark workload finishes, though in some cases the data won't be sent until the very end to avoid impacting the behavior of the benchmark workload (e.g. `pbench-specjbb2005`).

### Prometheus tools: `node-exporter` and `dcgm`

Two new pbench "tools" have been added, `node-exporter` and `dcgm`.  If either or both of these new tools is registered (e.g. via `pbench-register-tool --name=node-exporter --remotes=a.example.com`), then the Tool Meister sub-system will run the `node_exporter` code on the hosts (in this case, `a.example.com`) and a local instance of Prometheus to collect the data.  The collected Prometheus data is stored in the pbench result directory as a tar ball at: `${pbench_run}/<script>_<config>_YYYY.MM.DDTHH.mm.ss/tools-<group>/prometheus`.

For the duration of the run, the Prometheus instance is available on `localhost:9090` if one desires to review the metrics being collected live.

_**NOTE WELL**_: like all the other "tools" the `pbench-agent` supports, the `node-exporter` and `dcgm` tools themselves need to be installed separately on the registered hosts.

### The PCP tool

Just like the new Prometheus based tools, you can register "PCP" as a persistent tool using: `pbench-register-tool --name=pcp --remotes=a.example.com`.  This will cause each Tool Meister on the hosts for which PCP is registered to start a `pmcd` instance, and the Tool Data Sink will run `pmlogger` processes for each of those hosts to collect the data at the requested interval.

The new PCP support also allows you to register PCP as a transient tool, where it is started and stopped around each benchmark workload invocation.  The Tool Meister instance will also run the `pmlogger` process alongside the `pmcd` process to have the data collected locally, and will send the collected data to the Tool Data Sink instance when requested.  Use the name `pcp-transient` when registering (e.g. `pbench-register-tool --name=pcp-transient`).

_**NOTE AS WELL**_: like all the other "tools" the `pbench-agent` supports, the `pcp` tools themselves need to be installed separately on the registered hosts.


## Independence of Pbench Agent "tool" Scripts

The tool scripts the Pbench Agent uses to collect data can be run independently of the rest of the Pbench Agent so that users can verify they collect data as expected.


## Removal of Gratuitous Manipulation of Networking Firewalls

The manipulation of `firewalld` to open a port for the operation of `fio` by `pbench-fio` has been removed.  The user of `pbench-fio` must have already ensured that the ports specified for each client are open.  If using the default port (as configured in a `/opt/pbench-agent/config/pbench-agent.cfg` file), then the user should ensure that port (default is `8765`) is open.  If using the `--unique-ports` option, then the user should ensure that the range of ports for the number of clients are open (e.g. for `pbench-fio --clients=hosta,hostb,hostc`, port 8765 on `hosta`, port 8766 on `hostb`, and port 8767 on `hostc`).

Similarly, `pbench-uperf` no longer stops the host `firewalld` service before attempting to drive a `uperf` run.  The user should either stop the `firewalld` or open the ports used by `uperf` in `firewalld` (starting port is 20,000, then incremented by 10 for every server specified).

Finally, the Pbench Agent Ansible Galaxy collection provides roles for manipulating `firewalld` to enable the operation of the Tool Meister Sub-System, but those roles are not used by default.  The user must deliberately use those roles so that no fire wall manipulation occurs without their consent.


## Removal of Automatic Software Installation

The Pbench Agent provides software to collect data and meta-data from benchmark workloads and requested tools, and it also provides convenience scripts for running some benchmark worloads.  It is explicitly not a software provisioning system.

As such, the software required to run a particular benchmark workload, or a particular tool, is no longer automatically installed during the execution of the workload, or during tool registration.  If a benchmark convenience script or tool requires a certain version of software to be present, those checks will be performed and reported to the user as an error if the requirements are not met.

### Change to check command versions instead of RPM versions for `pbench-fio`, `pbench-linpack`, and `pbench-uperf`

The `pbench-fio`, `pbench-linpack`, and `pbench-uperf` benchmark workload convenience scripts no longer perform version checks against RPMs for the required software to execute.  For both `pbench-fio` and `pbench-perf` the reported version string is used from the benchmark workload command itself.  For `pbench-linpack`, the expected installation directory name is used.


## Enhancements to `pbench-linpack`

A new `--clients` argument has been added, given the user the ability to specify one or more hosts on which to execute linpack concurrently.

A new `linpack` driver script, which can be executed stand-alone, is now used.

Special thanks to Lukas Doktor for his work on implementing these changes.


## Required Use of `--user` with `pbench-move/copy-results`

In preparation for the forthcoming update to the Pbench Server, where the notion of a user is introduced and all result data tar balls are tracked per-user, the `pbench-move-results` and `pbench-copy-results` commands now require that the `--user` switch be provided.  This will help facilitate migrating data into the new version of the Pbench Server.  Users should choose a consistent value for `--user` and it should correspond to a favored user name they expect to select for the new server (e.g. an email address).


## Support for the New HTTP PUT Method of Posting Tar Balls

In preparation for the forthcoming update to the Pbench Server, support for sending data to a Pbench Server via an HTTP PUT method has been introduced. The new commands, `pbench-results-move` and `pbench-results-push`, provide that functionality.  A token must be generated for the given user via the new `pbench-generate-token` command.

The new `pbench-results-move` and `pbench-results-push` will not work with currently released versions of the Pbench Server (v0.69).  Please consult with a Pbench Server administrator for when the new version will be available for testing purposes and/or officially released.


## Removal of the Use of SCL (Software Collections Library)

For the Pbench Agent we have removed the use of the Software Collections Library (SCL) in order to provide a Python 3 environment for RHEL 7 & CentOS 7 distributions.  We now rely on the Python 3 provided with RHEL 7.9 and CentOS 7.9.

As such, the minimum supported version of RHEL and CentOS is 7.9.


## Support for `pbench-trafficgen` dropped entirely

With the release of v0.71, support for `pbench-trafficgen` has been removed in its entirety. It is too difficult to support the behavior of that benchmark workload given the implementation of `pbench-trafficgen` and `pbench-run-benchmark`'s trafficgen support.

Future work on supporting benchmark workloads will be approached by working to have the Pbench Agent integrate with separate software packages that are dedicated to running benchmarks (unlike the Pbench Agent which only provides convenience interfaces).


## Deprecation Notices and Removals

### Deprecated Bench Scripts

The following benchmark workload convenience scripts have been deprecated with this release and will be removed entirely in the next release:

| Benchmark Workload Convenience Script | Comments |
| ------------------------------------- | -------- |
| `pbench-run-benchmark` | This interface was never completed, and only duplicates existing functionality |
| `pbench-cyclictest`    | No replacement provided |
| `pbench-dbench`        | No replacement provided |
| `pbench-iozone`        | Consider using `pbench-fio` instead |
| `pbench-migrate`       | No replacement provided |
| `pbench-netperf`       | Consider using `pbench-uperf` instead |

### Other Deprecated Interfaces

 * The `pbench-cleanup` utility command is deprecated and will be removed in a subsequent release (see PR #1828)

### Removal of Deprecated Interfaces

 * Removed the deprecated `pbench-fio --remote-only` option


## Semi-Public CLI Additions, Changes, and Removals

There are a number of Pbench Agent CLI interfaces which are primarily used internal to the Pbench Agent code base, but happen to be made available alongside the other CLI interfaces.

Here are a few changes you should be aware of if you rely on any of these interfaces:

 * The `getconf.py` command is replaced by `pbench-config`
 * The following interfaces have been removed entirely and folded into the operation of the Tool Meister sub-system itself
   * `pbench-collect-sysinfo`, `pbench-metadata-log`, and `pbench-sysinfo-dump`


## Many, many, bug fixes and behavioral improvements

In addition to the major changes described above for this release, the following significant changes for the agent are also worth calling out specifically:

 * The release takes in the latest code from stockpile, including support for GPU data collection via the [Nvidia SMI](https://github.com/cloud-bulldozer/stockpile/tree/master/roles/nvidia_smi) role
 * Python based `click` CLI work towards "noun verb" structure
   * E.g. this shows up in the new `pbench-results-move`, `pbench-results-push` interfaces for the new HTTP PUT method of submitting tar balls to the Pbench Server
 * Fix the `oc` tool (`oc-datalog`) to properly reap its sub-processes
 * Fix for `user-tool stop` not working
 * Fix `pbench-fio`'s `ramp_time` template handling
 * Correct the behavior of `pbench-clear-tools`
 * Correct `pbench-fio`'s networking port use when the configuration file default port is changed
 * Correct metadata collected by `pbench-specjbb2005`
 * The `pbench-uperf` interface now supports `AF_VSOCK` operations via the new `--vsock-servers` option
 * Prevent `pbench-fio` from re-writing job files with the `--preprocess-only` option
 * Added support for operating systems which use sos (sosreport) v4.0 and later

ChangeLog
====

## What's Changed

You can review the [**Full ChangeLog**](https://github.com/distributed-system-analysis/pbench/compare/b0.69-bp...v0.71.0) on GitHub (all 560+ commits, tags `b0.69-bp` to `v0.71.0`).

What follows is an edited list of commits, newest to oldest, containing all commits which landed in the v0.71 release.  Note that of the 550+ commits, many of them are for the Pbench Server or Pbench Dashboard and are not considered for these release notes.

 * 0b7f55850 'Restore default tool set and deprecate (BP) (#2888)'
 * d699b2556 'Release Notes for `v0.71.0`'
 * f74a6629f 'Add numactl to agent dependencies - backport to b0.71 (#2881)'
 * 9d90a97cc 'Ensure use of `localhost` when stopping Redis'
 * acae28ba5 'Add local and remote pre-check for linpack'
 * afba7d5bc 'Stop resolving benchmark binary location'
 * 36263d0ee 'Handle response payloads which are not JSON in generate_token.py (#2862)'
 * 0a9d5ea4d 'Tweak container builds for CentOS 9'
 * 11f959b73 'Correct `pbench-specjbb2005` use of `-send-tools`'
 * 1675b63d8 '`pbench-specjbb2005` now handles commented props'
 * a46078d95 'Fix pbench-fio local fio-server execution'
 * e32b10e40 'Fix Tool Meister instance exit code handling'
 * 7c3f06522 'Add missing `f` letter for f-string'
 * 82b1ddfcb 'Correct spelling in `pidstat` tool help text'
 * 8c5cd16bc 'Backport quick fixes for v0.71 (#2829)'
 * e04e0aa09 'Backport testing of source tree builds'
 * 2035ccf1f 'b0.71 backport: Delete the spurious pbench3-devel RPM dependency'
 * b9a001e3e 'Use HTTPS for D3 loads (back-port)'
 * d5e7e2f02 'Enable CodeQL for `b0.71`'
 * c6d2267b1 'Use `b0.71` CI image tag for this branch'
 * 709637227 'Remove support for trafficgen'
 * 8a0aff524 'Improved `linpack` benchmark wrapper'
 * 5ba6e1872 'Deprecate unused benchmark convenience scripts'
 * b03914c49 'Fix unit testing for email_validator (#2776)'
 * 677330e24 'Add support for no registered tools'
 * 72e486993 'Remove unused mock for `pbench-metadata-log`'
 * 4b8fd19f2 'Refer to the Tool Meister sub-system'
 * 8a9f041f3 'Optional metadata should be optional'
 * bceae2c29 'Correct misspelling in `bench-scripts/unittests`'
 * ec4f148f4 'Remove unused `bench-scripts` mocks'
 * 2c579a21e 'Small changes deferred from recent PRs'
 * 6a96b5f50 'Simplify PID file names used by TM sub-system'
 * f530a34e3 'Refactor Tool Meister start to consolidate logic'
 * d629c7d75 'Employ a `NamedTuple` for TDS parameters'
 * ca91096c9 'Ensure `agent/base` is not used by Tool Meisters'
 * 4e66b1e0c 'Remove `pbench-sysinfo-dump` reliance on `base`'
 * 958779995 'Add a big-hammer redis server cleanup'
 * cc9f85f0a 'Remove unused `common` directories'
 * 536fd20eb 'Tabs to spaces, isle 5'
 * 5adaec345 'Get rid of the `pbench-perl-JSON-XS` dependency (v0.71)'
 * 53f0b84ba 'Move logic out of pbench-tool-meister-* files (#2741)'
 * 2c7250efa 'Add support for `--clients` to `pbench-linpack`'
 * f389cf860 'Remove `run_command` utility function'
 * da2a4fd7c 'Terminating benchmark run if tool rpm does not exist'
 * 8371a1266 'Record the Tool Meister data in Redis'
 * 6c90bf410 'Removed package-lock.json'
 * 9bb7a0365 'Code review feedback fixes'
 * 8545842b8 'Port various features from pbench-run-benchmark to pbench-linpack'
 * ed0ddfb46 'Refactor Tool Meister module, add `Tool` unittests'
 * 2bc36ea1c 'Update references for issues and projects'
 * bb52be206 'Ensure `args` parameter is sent on terminate'
 * 91156d293 'PBENCH-158 Wait for TDS to terminate gracefully (#2734)'
 * 01d8ae5fa 'Replace `sys.exit()` w `click._.exit()`'
 * df51866a9 'Replace `find_executable` with `shutil.which`'
 * 7ebddead6 'Re-try `tar` command if errors encountered'
 * 13b934727 'Remove `perf-fio-0` test directory when successful'
 * d440cb2df 'Correct `check_required_rpm` behavior'
 * 1227cb5b4 'Turn on CodeQL analysis'
 * b23c6cc10 'Add `relaxed` mode to `check_install_rpm`'
 * 4fdecaec1 'Ensure `${pbench_run}` directory exists'
 * 31bab838d 'Keyboard interrupt handling (#2713)'
 * 12c9ae839 'Initial Dashboard Code Base'
 * 11587d6a2 'Include "common" pytests in tox exec-unittests'
 * 3468bb17f 'Update to `black` 22.3.0'
 * c8801af44 'Normalize variable references in `agent/base`'
 * ad6fe1cd0 'Bring `BaseCommand` behaviors inline with `base`'
 * e4804a140 'Use `black` on some additional files'
 * c1f241de3 'Drop use of `--current-env` in CI jobs'
 * 23f9745b5 'Add linting support for agent ansible roles (#2701)'
 * 574daad69 'Create `pbench_run` directory IFF it is from the configuration file'
 * 0cf0e46b3 'Address lgtm.com recommendations'
 * 6b25b9c24 'Use debug-level environment variables (#2698)'
 * 2fcac2ccf 'Update to latest `black`'
 * b536f52cd 'Update to `flake8==4.0.1` (latest)'
 * c0b83313c 'Correct Tool Meister sub-process termination'
 * eb5ae2e52 'Use an explicit cache directory for pip installs'
 * cadcdc04b 'Remove refs to non-existent persistent tool files'
 * 9bee290d2 'Speed up source distribution creation'
 * 5740acf70 'Remove `ansible` from agent `test-requirements.txt`'
 * 44a3d6ad3 'Parallelize the python & legacy unit tests'
 * 63fa07ed5 'Fix a wayward server test'
 * efe48d9c3 'Remove references to logger method of base class'
 * eeec73fa5 'Revamp how we use tox to reduce envs'
 * 52102ac0a 'add bug report issue form'
 * 1f3d7b50f 'Remove refs to `pbench_results_redirector`'
 * 8204da055 'Ensure agent legacy unit tests pass'
 * 92254a76d 'Scrub the pytests'
 * 487f4baf1 'Remove persistent tmp directory on remote hosts (#2661)'
 * d167ab1d4 'Add pbench-run-benchmark.pl to the Agent's installed files list'
 * 66f23804e 'Support non-DNS controller hosts (#2643)'
 * 2b99341d9 'Run benchmark tool-meister related fixes (#2660)'
 * 702c17eb2 'Refactor development container builds'
 * b59a34a8e 'Simplify agent spec file (#2658)'
 * 9831f77f3 'Rework the agent functional tests (#2648)'
 * 22ed10283 'Add timeouts to tm start/stop test'
 * ac31569c6 'Construct redis pid file name once'
 * eedc4bae3 'Sort python requirements files'
 * 9b469cd74 'Fix oc-datalog to properly reap subprocesses'
 * 7dc1fd11a 'Stop using `selinux` virtualenv wrapper'
 * 25c569ddf 'Remove `BaseCommand` environment manipulations'
 * 494ebaf74 'Forward-port of `pbench-trafficgen` improvements'
 * 9ff58bd99 'Dump all .cmd files in bench-scripts unit tests'
 * 6ed993deb 'Clear up 'tool' vs 'tool_name' confusion in base-tool script'
 * a15c5d267 'Minimal fix for `user-tool stop` failure'
 * 0dabb2392 'Canonically determine local vs remote hosts/ips (#2542)'
 * 3e462efb8 'Update the Jenkins development container (#2640)'
 * dd5b53a10 'Improve Jenkins container run mechanism (#2639)'
 * 2acb76282 'Fix fio's "ramp_time" template handling'
 * 08c843676 'Fixes for pbench-clear-tools potholes (#2618)'
 * 8eed2aad6 'Use Bcrypt-Flask instead of Flask-Bcrypt'
 * 7d1ccfda8 'Use --all-ip-addresses instead of --ip-address'
 * 55efafd5c 'pbench-list-tools and pbench-register-tools inconsistency with env and config values (#2606)'
 * 1d87d1bbd 'Add option to allow chroot specs for COPR builds (#2622)'
 * ec1c58678 'Rework Agent containers build (#2607)'
 * 894ea5d0f 'Small improvements to `pbench-list-tools` and `pbench-clear-tools` (#2612)'
 * 1bf7ddb25 'Remove `pbench_run` parent directory creation from agent side `base` bash script'
 * ac57faaa1 'Remove test parallelism from Jenkins jobs'
 * 27d285e6e 'Execute the python cache cleanup in test context'
 * ea8388340 'Remove use of `podman run -it` switch by default'
 * 9abf5680c 'Fix umask problem with server legacy unit tests'
 * c17f05a2a 'Correct the plumbing of stderr and stdout in certain unit tests'
 * 18b3814d8 'TableOfContent (ToC) Server API (#2507)'
 * a8689ae43 'Add a warning message when no tools are registered (#2605)'
 * 7e503e21a 'Adjust dependencies (#2604)'
 * 64c3d74c9 'Remove controller parameter from queries (#2575)'
 * e8a684421 'pbench-copy-result-tb issue #2437'
 * 61cce010a 'Cleanup of agent ansible roles (#2594)'
 * d5b6e0774 'remove adding unnecessary paths using pathins'
 * c68c4c14c 'use pathins function to update system path'
 * 97a402cfd 'make sure /usr/sbin is present in system PATH'
 * f3368d1c9 'Review feedback'
 * 735141769 'Add support for a containerized Pbench Server'
 * ff025f3b5 'Add dependency on Dashboard RPM to Server RPM spec file'
 * 076edb01a 'Add receipe for building a RHEL 8 development container image'
 * 8629979e9 'Remove implicit use of "quarantiner" user (#2591)'
 * 93f1c9908 'Pick lint'
 * 54dc85e8c 'Even yet more additional review changes'
 * a205435a4 'Maybe possibly final refactoring?'
 * b6bfea652 'More feedback refactoring'
 * 46bbed3cd 'Yet more review comments again'
 * 6643ca0ed 'More refactoring and unit test cases'
 * c52ee3414 'Refactoring and cleanup'
 * c756e0c0a 'Dataset DELETE'
 * 8f09652ae 'Add selinux to the Server requirements.txt file'
 * db58dc0c3 'Add cronie and copr-cli to Jenkins dockerfile'
 * 512e47dce 'Add explicit cron dependency to Server spec file'
 * b09063798 'Rework Server restart interval and correct .service file permissions'
 * ac96b7bae 'Harden prep-shim against running with SELinux disabled'
 * acb3fc470 'Spec file and ansible fixes for RHEL9 (#2556)'
 * 86035433d 'reorder imports and API endpoints'
 * 4c9d36f0d 'Nomenclature update index->dataset'
 * 271c318ed 'fix hardcoded index name in commons.py (#2581)'
 * 13c20cbe3 'Move index_mappings api to appropriate directory (#2561)'
 * adb1985d2 'Add missing 0.69 agent generated metadata'
 * be8ac3460 'Dynamic `root_index_name` (#2572)'
 * 84f3dbdb9 'Adding ssh for creating hostname directory on Host machine'
 * 43c27375a 'TimeSeries document query API (#2534)'
 * d84422d69 'Require `--user` for `pbench-move/copy-results`'
 * 1037cec6b 'pbench-register-tool: treat an empty remotes file as an error'
 * 96cbc200d 'Post deprecation notice for unsupported benchmark scripts'
 * 53a923bb3 'Add `hiredis` requirement for performance reasons'
 * 2492cf9c4 'Remove deprecated `--remote-only` pbench-fio option'
 * 32798dbe2 'Replace RPM version checks with `fio --version` and `uperf -V`'
 * 2494f02c8 'Remove use of `wc -w` sub-process'
 * b6662df6e 'pbench-register-tool-set: check for bad remotes file (#2514)'
 * 7bb378bd5 'pbench-fio: drop use of `sed` for comma replacement'
 * 37ebd7d76 'Refactor `pbench-uperf`'
 * ec00458a1 'Increase Prom retention to `1yr`'
 * 9b6edceaa 'Fix `/api/v1/endpoints` in container environment'
 * c2bdfafcf 'Improve grammar in `test-bin/java`'
 * 0a39cc069 'Fix grammar in `test-56.pre`'
 * f6be81f5e 'Stop explicitly manipulating firewalls'
 * 35b324fee 'Iteration samples query API'
 * 236261d65 'Correct `pbench-fio --client` handling'
 * 6a02d8587 'Fix specjbb mdlog (#2522)'
 * 84a5d628f 'Ensure fio usage msg sent to stderr as necessary'
 * 3cb599197 'Ensure `pbench-fio` exits w/ non-zero exit status'
 * 3bf9c9695 'Ensure `fio` uses full unix timestamps'
 * 58eb66433 'Add the use of '...' in help text output'
 * aef8d1a85 'Enhance `pbench-fio --targets` help message'
 * f7a3e0b57 'Implementation of user & access query semantics'
 * 8dfc49243 'Add support for vsock to the pbench-uperf script'
 * 9f823451b 'Add variable for the pbench repo name (#2513)'
 * eb9142cf2 'Make the default tool set lighter (#2390)'
 * 91eefd2d8 'Convert to Elasticsearch streaming_bulk helper (#2492)'
 * aa72535f1 'Cleanup in JSON parameter handling (#2504)'
 * c55729f55 'pbench-list-tools: new output format and error handling (#2493)'
 * 29f2e0483 'Tweaks for Jenkins Raise the time limit on Agent postprocessing performance tests to accomodate occasional resource crunches on the executors. Correct the Jenkins pipeline to avoid losing failure statuses.'
 * 529ca6c01 'Correct Cobertura coverage report location in Jenkins'
 * 467a4f02e 'API for iteration sample documents'
 * 936c2ed07 'Add big fio performance test'
 * a7de09c4b 'Add performance evaluation'
 * fb1ca9741 'More refactoring'
 * f7ee547a1 'Refactor the tool scripts postprocessing unit test script Remove the reference-result symlink from the process-iteration-samples-0 gold Remove the metrics.csv file from the haproxy-ocp gold, since it is an input'
 * c36d41663 'Changes to spec file and reqs (from jam session 2021-10-07)'
 * 0df21bbb3 'Rework Jenkins Dockerfile to make the dependencies easier to manage And update the comments'
 * 4b14fbab2 'Update Server RPM dependencies'
 * 5c0f7376b 'Remove explicit removals from RPM removal'
 * 1ffce5e5e 'Adding pbench image test/demo script'
 * 517eaa9d7 'Add dataset Metadata needed for Overview Page (#2417)'
 * ba3cae8e7 'Canonicalize the JSON output from trafficgen-postprocess'
 * 0cecb5f72 'pbench-list-tools: add tests and fixes for exceptions'
 * a53ddebd7 'Remove unused BenchPostprocess functions in linpack-postprocess Also, other small changes.'
 * 1d314d6dd 'uperf-postprocess whitespace changes'
 * a725ee598 'Rework result post-processing This change modifies the support in BenchPostprocess.pm to expect timeseries data in the workload hash to be a hash of hashes, using the timestamp as the key instead of an array of hashes.  This ensures that each timestamp is unique, and it makes each timestamp's data accessible in constant-time rather than requiring a linear (O(n^2)) search.  For large datasets, this results in a dramatic improvement in execution time for producing the aggregate results.'
 * 5ee987703 'Reformat trafficgen-postprocess and process-iteration-samples'
 * 1f2a41564 'Add unit test for post-process only with no directory'
 * cdd2b6190 'Tweak pbench-fio to handle missing samples'
 * 9bcfab361 'Do not re-write fio job file in post-process only mode'
 * 86a4a61ec 'Add a script for building and installing Pbench in a container Rework jenkins/python-setup.sh for containerized execution.'
 * 0cd8e2f26 'Tweak jenkins/run Change the volume mapping for the source directory from /home/pbench to /src/pbench, to avoid collisions with the Server RPM installation, and remove the mappings for /tmp and /var/tmp which seem incompatible with running other, non-root users inside the container. Add hook a for adding podman switches'
 * 42176caba 'Prevent pbench-config from finding the Agent config for Server unit tests'
 * 109a3c5b3 'Fix small RPM build issues'
 * 53839cc47 'Update the Jenkins container to Fedora 33'
 * 9c2b1ed57 'Make tools list deterministic'
 * e5c4dbde1 'Miscellaneous infrastructure fixes from v0.69 branch'
 * a9a32a43a 'Correct checking for required tool packages'
 * 556dd252e 'Check for the `ansible` RPM for the `pprof` tool'
 * 5267d9cbf 'More installation cleanups (#2452)'
 * 8e186271c 'Tiny syntax error fix'
 * 7552b8575 'Add malformed authorization unit test (#2442)'
 * 5f355374d 'Refactor ElasticBase to expose framework elements (#2438)'
 * c4dcdff0b 'Refactor `results-move` and bring to parity'
 * 833013e5f 'Server installation cleanup (#2423)'
 * c179c8f86 'Fix unit test date_range method (#2439)'
 * 09b1510a9 'Add tests for admin role access (#2430)'
 * f3a1d1fe5 'Search API based on query string pattern match'
 * 5e1eea6b1 'Remove use of `ssh -q` and improve error messages'
 * 63f9195c2 'Use batch-mode for all `ssh`/`scp` operations'
 * 2cdfe7ada 'Replace tabs w spaces only'
 * 8bc97e259 'Add psycopg2 RPM to Jenkins container (#2428)'
 * 8f1f0f75a 'Remove redundant query API test code (#2413)'
 * 4b0a05e2d 'Fix stand-alone use of `pbench-make-result-tb` (#2405)'
 * 2e81422a6 'Remove write permission on agent installed files'
 * 444b7d668 'Documents index mappings query api (#2382)'
 * 6f33c320e 'Correct `tracker` module name (#2409)'
 * 104d308ff 'Publish dataset API (#2355)'
 * 7531e2bd3 'Fixes for sos-report >= 4.0 versions'
 * 37ba47ee2 'Ensure redis does not persistence any data'
 * 00f9de02d 'Add optional authorization header requirement on es APIs (#2251)'
 * b39ab74e8 'Add gunicorn worker timeout and replace all http numeric status (#2359)'
 * dee20234d 'Some Refactor and change http codes to use symbolic names - Return Not_found instead of Forbidden to an admin user if no target user found - Allow admin user to delete other admin users except themselvs, add role to protected fields'
 * 549267bd2 'Click group functionality to tie all four server side cli commands - pbench-user-create - pbench-user-delete - pbench-user-update - pbench-user-list'
 * d6ef508df 'More cleanup.'
 * 84b58bf92 'More query_api unit test cleanup and refactoring'
 * 3f8bc6a99 'Query fixes'
 * 5af852973 'Handle `ENOSPC` and report exceptions once'
 * 23f339b49 'Clean up LGTM complaints (#2315)'
 * b796c5cf5 'Add support for `PBENCH_ORCHESTRATE` env variable'
 * 960494783 'Remove unneeded `pipenv` invocation'
 * 35528da20 'Properly collect host name information'
 * 18fe25d1d 'Validate all passed in `_pbench_hostname_ip` values'
 * 971b873d7 'DRY out metadata log file command and library'
 * 0a98eb369 'Turn off interpolation of `metadata.log`'
 * 04c73dad2 'standalone db.init should import all the models'
 * 40c8318d4 'Refactor use of `check_install_rpm`'
 * e9c890b47 'Correct minimum RPM version support'
 * 27d6dea30 'Allow live metric visualization for remote runs + Added customizable hosts/ports + Updated pcp visualizer and cleaned all'
 * da535ac52 'Add messages to assertions'
 * 890f585a1 'Code review feedback'
 * 0e84378e3 'Ensure that tarball upload gets desired HTTP headers'
 * 370b6639b 'Small black formatting fix'
 * 87c6b9118 'Separate logger name from module name'
 * 43558b3c1 'Rework upload API to move filename to URI'
 * 2b0064f94 'Index documents by user ID instead of username. (#2291)'
 * 8286a1735 'Refactor PbenchTemplates'
 * d41cda01a 'Add python3-psycopg2 require in the server spec file'
 * 5fdd39804 'Add a role to install the EPEL repo'
 * f6d82bf61 'Add expected exit status to unittests failures'
 * 27e043d47 'Add the `Content-Length` header to the PUT req'
 * 5be8b0a09 'Allow positional arguments for pytest'
 * 048718100 'Improve error handling in Elasticsearch queries'
 * a4bb48d0a 'Quiet Redis server connections by default'
 * a3363d041 'Make pip install into  %{installdir}'
 * d5d249889 'Visualizer update + bug fix'
 * 4f154b4d7 'Replace use of become/become_user with remote_user'
 * cdea20255 'Update PCP repo for container builds'
 * e31b471d8 'Fix CentOS 7 / RHEL 7 pbench-agent installations'
 * 2f3ecfb9e 'Add Authorization header to upload PUT API and address issue 2240'
 * 745348012 'Add pbench-results-push command Create a new, Click-based command which uses the server's HTTP PUT request to upload result tarballs.  This command is intended to replace the existing pbench-copy-result-tb script.'
 * bd5d0657b 'Simplify and consolidate Elasticsearch queries'
 * 74ec53066 'Correct `pbench-tool-meister-client` & `-stop`'
 * 5794fc1db 'Enable minimum RPM version support'
 * a875e8716 'Share mocks between persistent tools'
 * 1bc430598 'Only measure coverage in `lib/pbench`'
 * c4280f9fd 'Ensure we always pull jenkins devel images'
 * e9541386f 'Don't validate params for pbench-fio install'
 * 81bb524a1 'Add role column in user table'
 * c9dd0e971 'Refactor tool-meister-start orchestration'
 * b9252491d 'Add pbench create user cli'
 * 1ec73082d 'PCP Transient Tool Update  - Introduces a transient option for the pcp tool  - Also adds new tool register options and naming conventions     - `--transient` and `--persistent` upon registration'
 * 6d7ec910a 'Add missing validate-* scripts'
 * 2d7961991 'Add hostname and IP address validation for env'
 * 100f349d1 'Refactor Elasticsearch template management (#2206)'
 * f6777899a 'Userdb (#2101)'
 * 76d876e98 'return same status code for bad username and bad password'
 * ea029952a '.gitignore change'
 * dc48a160e 'fix logout response workflow'
 * 8c3a10249 'Unify agent and server RPM builds (#2187)'
 * 03e4a14c3 'Sort setup.cfg'
 * 69f727390 'New dcgm-exporter update with visualizers'
 * 2e8fe9453 'Expose PCP ports; correct firewall files'
 * 8e07c53a9 'Use the PCP "bintray" repos for PCP RPMs'
 * 438d3ec13 'Containerization of TM and TDS'
 * c3ce54e32 'Add missing distro targets to the Makefile'
 * 072e9322b 'Add dependencies to pbench-devel required to build RPMs'
 * 735d8b5b1 'Fix pytest-helpers-namespace at 2019.1.8'
 * 27284d70f 'Improve diagnostic for connection error in pbench-generate-token'
 * cf66c5389 'fix login workflow, unit test for extrenal auth_token update'
 * 3912bb79f 'Tweak to log output'
 * 58540aaa5 'Review comments & cleanup'
 * fd8c61b41 'Change to dynamically construct API set from Flask'
 * 70b2693d6 'Move to automatic reverse-proxy configuration'
 * 513a51438 'Rebase'
 * f0b012df7 'Add support for reverse proxy configuration'
 * 6c672121f 'Add endpoint configuration query'
 * d707c7391 'In agent makefile, put Click-based tools in their own install list and add pbench-generate-token to the list'
 * fbf866829 'Add pbench-generate-token'
 * 68cf5f47d 'Replace deprecated hyphens with underscores in setup option names'
 * 3a2d1ca2d 'Tweak Click options for agent config command line option'
 * ec753ac1f 'Fix docstring typos'
 * 2fd5f3c8f 'Add firewalld service files'
 * 9c2268cfb 'Remove use of podman by Tool Meister subsystem'
 * b95c73bcf 'Ignore annotated coverage files'
 * 33027e832 'Refactor Tool Meister infra for data capture'
 * ee28a87e1 'Build state tracker (#2074)'
 * 6f41da408 'Obsolete exception SosreportHostname & TarError (#1782)'
 * bded8bc81 'Fix es url formation when params exist in json data (#2133)'
 * 8caf11d5b 'Initial pbench user authentication model implementation (#1937)'
 * 4c96c4252 'Add SIGHUP handler to pbench indexer (#2114)'
 * a0a3289b2 'Streamline server RPM spec file (#2124)'
 * cca4629b9 'Setting SELinux labels correctly'
 * 0e7a388a3 'Fix unused variables from lgtm bot'
 * 89eef7717 'When installing the server, set the host-info state to maintenance'
 * 7090c1b7c 'Exclude site-packages from coverage report'
 * d2dd5ffb6 'Support original version strings for HammerDB'
 * b55b3a15a 'Update server test-7.24 showing failure case'
 * ef5555d29 'Cleaner path'
 * b0646d4d7 'Added PCP post-run visualization'
 * 0b99487c6 'Fix turbostat for real this time'
 * e7a15c15c 'Fixes #1938'
 * 01b4cbd5a 'Ensure pbench develop install occurs for tests'
 * e1b89a928 'Remove non-existent coverage tox environment'
 * 210b5c5a8 'Fix use of date parsing in query API'
 * 68a055bbc 'Run pbench-server systemd service as a pbench user'
 * d4390906f 'Add containerized data visualizers'
 * 6673fe220 'Initial unit tests for pbench-run-benchmark'
 * a0fa55148 'Fix pbench-gen-iterations whitespace & comments'
 * 5813b5cd6 'Refactor to fix trafficgen UIDs'
 * 4fa811c6b 'Fix whitespace issues in process-iteration-samples'
 * 5294efeac 'Add `--unique-ports` to pbench-fio'
 * ea4ec2079 'Default configuration for Apache reverse-proxy from port 80'
 * 3932f50af 'Add 99.5 percentile support'
 * 1d7000030 'pbench-fio: compute localhost latency profiles'
 * db0413ab9 'Fix tabs vs spaces for option processing'
 * cb7b3997a 'Add a README.md for the agent/rpm directory'
 * 554b8838d 'Fix flake8 issue with variable name'
 * b019c8891 'Treat files with suffix .tgz, .tar, or .tar.<something> as tarfiles'
 * 8795350d6 'Fixes #1681'
 * 16f552241 'Containerized Implementation of PCP in Pbench Agent'
 * 50e034765 'Modifications to template data types for dashboard'
 * 3eb5efd19 'Correct locale issues with CentOS 8'
 * 7c522a32e 'Fedora 33'
 * 0e7ddb487 'Wrapper for pbench-run-benchmark to get ENV'
 * b5e4d03dd 'Fix move results ssh loop'
 * 8305ab9a4 'Add coverage support'
 * 57d5de82d 'Fix ulimit problem in postprocess tests'
 * 3435875c3 'Revert "Fix ulimit problem in postprocess tests"'
 * 928d24324 'Revert "Add coverage support"'
 * d51f3c4ba 'Revert "Fedora 33"'
 * ca0f0b84f 'Revert "fix py3-agent to match py3-server coverage location"'
 * 075e4a98a 'fix py3-agent to match py3-server coverage location'
 * 4e9a2e856 'Fedora 33'
 * 1758f27da 'Add coverage support'
 * 27463ee46 'Fix ulimit problem in postprocess tests'
 * f74a4c3b6 'Fix issue with stranded pidstat and turbostat'
 * 65643e9ba 'Remove unnecessary pbench module dependency'
 * f76e76f26 'Ugly - pbench-register-tool-set bad for perf'
 * 8d7d90eee 'Correct file permissions for fio-shared-fs.job'
 * 06d3993a2 'Stablize the pprof unit tests'
 * 02f2fe38d 'Add missing "g" to commit id field in the server config file'
 * 1666714ce 'Address lgtm.com errors'
 * abab42d06 'CORS fixes and a new API'
 * e4ddee528 'Add unit tests for pbench-clear-tools'
 * 95467c22c 'Fix bug when reading a file in chunks'
 * 8e14bd256 'Fix py move-results to use `ConfigParser`'
 * 28cb5b182 'Fix SysLogHandler reference'
 * 893b51472 'Fix logging for Tool Meisters'
 * 200de32e2 'Pythonize pbench-register-tool-trigger'
 * dcb6ed201 'fix extra trailing parantheses when gunicorn app starts'
 * 315ce8fca 'Fix server spec file'
 * 4f5706075 'Fix bad jenkins "pytests" runs'
 * 4b4a7218b 'dropdown text sync'
 * c013d65a4 'dropdown cards added'
 * c1c98058e 'Sphinx Basic setup and pbench-guide added'
 * 13afd082e 'Remove the `pbench-agent-config-*` scripts'
 * a5cec0864 'Fix spec file and ansible roles'
 * a9701380a 'Refactor server api implementation'
 * 582179b39 'Replace pbench-clear-tools tests'
 * e33666b59 'Prometheus quick fix'
 * 33dfb569b 'Use `ssh_opts` when starting remote tool meisters'
 * 787b48c65 'Add support for overriding TM bind hostname'
 * 95b391a5f 'Finish to remove agent user/group'
 * 51851f537 'Pythonize pbench-list-tools'
 * efb136dcf 'Have to handle empty variables, too'
 * 7035e54eb 'Add newline instead of a space'
 * bc467529d 'Harden against spaces in file names'
 * f13780738 'Pythonize pbench-clear-results and pbench-cleanup'
 * 92117c0c1 'Fix util-scripts test-34'
 * ef98b8fd4 'Phase 2 of generate-pbench-timeseries-graphs:'
 * 455b9dcae 'Add support for sysinfo via Tool Meister'
 * 40fb7c640 'Stop using f-strings with logging'
 * 670464656 'Remove unnecessary explicit 'object' sub-classing'
 * 342db667d 'Add `--controller` option to `pbench-move-results`'
 * 96ee7557f 'Clean up dangling files test files'
 * d06f61965 'Pbench support for Elasticsearch V7'
 * 3b3beaa60 'Fix the Python 3 logger to handle time properly'
 * 41ebcfee5 'Remove the pbench user and group from the agent'
 * 6986c8d89 'Pythonize pbench-list-triggers'
 * 8bb4bef2a 'Fix typos, grammar in *.md files'
 * f0c9aa023 'Correct the `PYTHONPATH` for Jenkins jobs'
 * f7824d053 'Enhance `tool-scripts/README`, `doc/CONTRIBUTING`'
 * ad3e4d390 'Generate time series graphs from pbench .csv files'
 * 659d90d11 'Add missing `net-tools` req agent RPM'
 * 13e931db3 'Remove colorlog; add Makefile for pbench-devel'
 * 13514767d 'Rework pass-thru API implementation a bit'
 * 2695e8e2a 'Jenkins integration using Fedora 32 container'
 * 853f67905 'Fix the flaky util-scripts test-51 & test-52'
 * 57808c798 'Address common logging between agent and server'
 * 6be975825 'Fix agent side `test_move_results`'
 * 4746adb79 'Use `_pbench_` prefixed env var for host names'
 * 99ed63986 'Make sure we explicitly ask for the full hostname'
 * 9b1d6465e 'Refactor base to extract unit test overrides'
 * a86cbb6af 'Address some undesirable tox behaviors'
 * 72733736f 'Fix misaligned deps in tox.ini'
 * 201988e3a 'Direct `black` to ignore `.git` subtree'
 * f8ae42194 'Cleanup `datalog/prometheus-metrics-datalog`'
 * b9f2dbc30 'Rejig functional unit tests'
 * bc50b7223 'Fix warning while running unit tests'
 * 82c193a8a 'Add ability to tag agent images with beta and alpha'
 * 8d7fa14ef 'Rejig the agent logging'
 * 3a851f844 'Remove colorlog'
 * 16123734e 'Require pyesbulk 1.0.0 for now'
 * 70ddd8a2d 'Add changes from PR #1916'
 * 7f614fe04 'Remove SCL from the agent side'
 * 2c63c88b3 'Remove SCL reference in the server trampoline code'
 * afa0de0ef 'squash me - feedback comments addressed'
 * 4db97e7ea 'Fix the README to restore working URLs'
 * 04e1442cd 'Enhance agent container builds'
 * 805cc590d 'Add required package name for vmstat'
 * 62e192ec8 'Remove use of `screen` from Tool Meister'
 * 511e60d4c 'Account for new pbench-clear-tools'
 * 86a34aef0 'Only do git submodule init at the top of the tree'
 * 09e0cdc0a 'Pythonize pbench-clear-tools'
 * 0be7499e2 'Stop invoking screen directly in unit tests'
 * 7cd23f6d2 'Remove wayward py3-functional unit test'
 * 37a70227b 'Source agent `base` for remote tool meisters'
 * 04c0a0356 'Record the pip3 command output to a log file'
 * a0e861791 'Add warning for left-over `id_rsa` file'
 * 615c5f056 'Encapsulate building the final requirements files'
 * f4e1d74d4 'Don't `%ghost` `id_rsa`; only `rm` in `%postun`'
 * db0cce542 'Move to rh-python38 for RHEL 7 & use python RPMs'
 * caa6f71a7 'Add redis and python3-redis agent RPM requires'
 * 3e8597e41 'Add a "common" unit test environment'
 * 3805b8303 'Move md5sum() method to common utils'
 * d8ea23498 'Don't remove `id_rsa` and `pbench-agent.cfg` when uninstalling'
 * 0927dc4e0 'Remove blanket executable file permissions'
 * 034f1f546 'Use the %config for the agent config file'
 * 916ce34af 'Ensure proper use of rh-python36 only for RHEL 7'
 * 73ccffc05 'Remove pbench-agent RPM dependencies for tools'
 * fcea38c68 'Update minimum supported Fedora to 31'
 * 13844f398 'Update pbench-agent spec file summary & desc'
 * d687e8f02 'Add use of `rpmlint` on `.spec` files'
 * dc9d0c5d4 'DRY out run-unittests, adding one for the server'
 * b6a209da7 'Create the notion of a utils directory'
 * cb6af9c99 'Open main branch targeting v0.71'
 * d4386635d 'First pass at a container image for the pbench-server'
 * fdda13808 'Making a server RPM (without SCL)'
 * 720e6c373 'Initial pbench-agent container image layering'
 * 20a307e90 'RPM making for pbench-agent'
 * 3aa69d651 'General method of fetching git commit ID'
 * 59d1989e2 'update agent cli to reflect server upload PUT changes'
 * 3526a76a3 'Additional changes to break up testing requirements'
 * 80c4b7e24 'Break up agent & server requirements'
 * c29f7caac 'Resolves logging error in pbench-server-prep-shim'
 * ed39d86c7 'Fix missing space in sosreport --quiet option'
 * f32e0fddb 'write md5sum of a tarfile on disk on server and add upload POST to upload PUT'
 * 7d122d20c 'Fix pbench-clear-tools based on new unit tests'
 * 736bd2738 'Fix handling of expected exit status in unit tests'
 * b03cddd27 'Remove , add periods in pbench-clear-tools'
 * 2b8df4dbe 'give pbench user access to /run/pbench-server directory'
 * 202148460 'Deprecate pbench-cleanup & add tests for clear-results'
 * 3d0d1f402 'Switch legacy unit tests to use C.UTF-8 locale'
 * 79086b46b 'Updated benchmarks wit init/end'
 * f72e16ebb 'Add unit tests for filesize_bytes'
 * 52e0f9703 'Reformat the upload api test and fix stored md5sum of log.tar.xz'
 * c32596fc7 'Fix util-scripts test-53'
 * 33ee31919 ' Post-Merge Review Changes (#1839)'
 * 8bca118c0 'Prevent server unit test `test-25` from failing'
 * ae03d28e6 'Fix generation of sosreport command'
 * a27edb09c 'Ensure Tool Data Sink internal server object exists'
 * 966333058 'Tell pbr to stop creating AUTHORS & ChangeLog'
 * 276df1ab8 'Fix bad printf statement in server/test-find-behavior'
 * d10ab00fb 'Add missing quote'
 * f66e8e574 'Early prep for the 0.70 release'
 * 4775f1d82 'Add gunicorn wsgi server configuration'
 * 9c29bc038 'Added DCGM Tool to pbench-agent (keshavm02)'
 * cb3434e8c 'Prometheus/Node_Exporter Full V1 Integration Commit'
 * a6c5890b9 'Sort modules in *requirements.txt'
 * 637c4f3bc 'Lock in use of Perl 5.30+ for Travis CI'
 * 0e7f70691 'Setup base class'
 * 20bfd2b94 'Pbench-server API improvements'
 * 30d2246cc 'Pbench Server API'
 * c0e938022 'Clean up the sosreport version number checking'
 * ed6d80460 'Record the sosreport command that was used'
 * 4f5e6ee58 'Fix bench/util-scripts unit tests env overrides'
 * ac69d6607 'Perhaps useful script for updating gold files'
 * d32a0913b 'Switch indexer.py to pyesbulk package'
 * 64bcdbb29 'Minimal attempt to remove tool meister commands'
 * 01d17fce0 'Only emit a warning message on missing debugfs'
 * 4ee7dd9c6 'Fix tool argument handling'
 * 61da5dcaa 'Tweak tool meister tests to use multiple tool opts'
 * 94e42e5ab 'Ansible role for systemd service'
 * b5a48712d 'Fixes to the systemd service file plus a service file for RHEL7'
 * ad9eb15d9 'Make shell.py into a package that exports a main().'
 * 4222d0f5c 'A few more cleanups'
 * d4c6a440b '- Make all non-environment variables local to functions named _pbench*'
 * 23cc097e2 'First pass implementation of the "Tool Meister"'
 * d8f835dd8 'Prepare roles for Ansible Galaxy'
 * 991ad99dc 'Set backup cron job frequency to every minute'
 * 1fae07131 'Make spelling of commit_id consistent'
 * 164320525 'Fixes issue #1668'
 * d382a8da2 'Lock versions of flake8 and black to known-good (#1768)'
 * 80c8d8e2f 'Give default values to most of the variables.'
 * 5048a1496 'Require fio 3.21 and later'
 * 98beb1086 'Fix uperf "rr" (round-robin) test XML'
 * 2561f44bb 'Rename pbench-agent.cfg.example to pbench-agent.cfg'
 * b8cb2b81f 'Avoid hardcoded tools location on bench-scripts'
 * 681574357 'pbench-server-prep-shim-002 into python program'
 * dbfb7f7ed 'Fix project name to Pbench.'
 * c3002f161 'Fix tabs vs spaces in agent/base'
 * ff58abbb2 'Fix formatting of contribution guide'
 * 0180aad73 'Use Python 3's pathlib where possible'
 * bf382c23f 'Fix datalog-cpuacct directory order'
 * 47edfa80d 'Sort the output of pbench-cull-unpacked-tarballs.py'
 * 500a73713 'Change ToC `parent` field to "keyword"'
 * 8a00fe158 'Get rid of sudo requirement'
 * 4a06bd46b 'Refactoring to introduce PbenchAgentConfig class'
 * 5b3874a50 'Implement PbenchConfig base class'
 * f9ae8a845 'Move server side logging to common'
 * c2661dcb5 'Run agent side test directories individually'
 * d142d16d4 'Remove explicit sub-classing of `object`'
 * 2ee00fcb5 'Change pbench-dbench to stop using /tmp'
 * 9d428afa8 'Add py3-functional to run-unittests'
 * b07c678c0 'Restructure pbench namespace'
 * 127eb7c02 'Add config options and debug options for agent'
 * 77fa536d0 'Refactor pbench-cli'
 * d44f0b595 'Centralize agent results classes'
 * b8958d312 'Centralize click options'
 * 3e9b9c6a5 'Search for agent configuration'
 * a18fc933a 'Add unittests'
 * 32d3f285f 'Remove getconf.py for server'
 * 59ce3bcdf 'Remove getconf.py for agent'
 * e0e65709c 'Add pbench-config cli'
 * c16ada514 'Refactored pbench server and agent code'
 * af4feecc5 'Formatted scripts using f-strings'
 * c1b4e1376 'Added script specific and default logging level'
 * 1c91c895c 'feat: pbench-server REST API'
 * 6b082d48f 'Setup pbench namespace'
