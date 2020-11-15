v0.70.0 (Beta) Release Notes
====
This is a very *significant* "minor" release of the pbench code base, agent and server.

The "Tool Meister" functionality (PR #1248) is the major piece of functionality delivered with this release.  This is a significant change, where the pbench-agent first orchestrates the instantiation of a "Tool Meister" process on all hosts registered with tools, using a Redis instance to coordinate their operation, and the new "Tool Data Sink" handles the collection of data into the pbench run directory hierarchy.  We effectively eliminate all remote SSH operations for tools except one per host to orchestrate the creation of the Tool Meister instance.

The Tool Meister work has enabled us to integrate with Prometheus for tool data collection.  Two new pbench "tools" have been added, `node-exporter` and `dcgm`.  If one registers either or both of these new tools (e.g. via `pbench-register-tools --name=node-exporter`), then the Tool Meister sub-system will run the `node_exporter` code on the registered hosts, and a local instance of Prometheus to collect the data.  The collected Prometheus data is stored in the pbench result directory as a tar ball at: `${pbench_run}/<script>_<config>_YYYY.MM.DDTHH.mm.ss/tools-<group>/prometheus`.  For the duration of the run, the Prometheus instance is available on `localhost:9090` if one desires to review the metrics being collected live.

_**NOTE WELL**_: like all the other "tools" the `pbench-agent` supports, the `node-exporter` and `dcgm` tools themselves need to be installed separately.

Along with the delivery of the "Tool Meister" work, the notion of tool registration has changed significantly, where tools are now recorded as registered only on the local host were `pbench-register-tool` and `pbench-register-tool-set` are invoked.  As a result of this change, the following behavioral changes follow:

 * The process of registering tools on local or remote hosts no longer validates that those tools are available during tool registration
 * All tools registered prior to installing `v0.70.0-beta` must be re-registered; tools registered locally or remotely on a controller with a version of the `pbench-agent` prior to `v0.70.0` will be ignored until they are re-registered

For both the Pbench Agent and the Server we have removed the use of the Software Collections Library (SCL) in order to provide a Python 3 environment for RHEL 7 & CentOS 7 distributions.  We now rely on the Python 3 provided with RHEL 7.7 and later.

We did not bump the "major" release version number with these changes because we still don't consider all the necessary functionality in place for such a major version bump.

Installation
====
There are no other installation changes in this release: see the [Getting Started Guide](https://distributed-system-analysis.github.io/pbench/start.html) for how to install or update.

After installation or update, you should have version `0.70.0-9ga7d1f0d6` of the `pbench-agent` RPM installed.

RPMs are available from [Fedora COPR](https://copr.fedorainfracloud.org/coprs/portante/pbench/), covering Fedora 31, 32, EPEL 7 & 8.

There are Ansible [playbooks](https://galaxy.ansible.com/pbench/agent) available via Ansible Galaxy to install the `pbench-agent`, and the pieces needed (key and configuration files) to be able to send results to a server.  To use the RPMs provided above via COPR with the [playbooks](https://galaxy.ansible.com/pbench/agent), an inventory file needs to include the `fedoraproject_username` variable set to `portante`, for example:

```
...

[servers:vars]
fedoraproject_username: portante

...
```

Alternatively, one can specify `fedoraproject_username` on the command line, rather than having it specified in the inventory file:

    ansible-playbook -i <inventory> <playbook> -e '{fedoraproject_username: portante}'

_**NOTE WELL**_: If the inventory file also has a definition for `pbench_repo_url_prefix` (which was standard practice before `fedoraproject_username` was introduced), it needs to be deleted, otherwise it will override the default repo URL and the `fedoraproject_username` change is not going to take effect.

While we don't include installation instructions for the new `node-exporter` and `dcgm` tools in the published documentation, you can find a manual installation procedure for the Prometheus "node_exporter" and references to the Nvidia "DCGM" documentation in the [`agent/tool-scripts/README`](https://github.com/distributed-system-analysis/pbench/blob/b0.70/agent/tool-scripts/README.md).

Container images built using the above RPMs are available in the [Pbench](https://quay.io/organization/pbench) organization in the Quay.io container image repository using tags `beta`, `v0.70.0-9`, and `a7d1f0d6`.

Agent
====
In addition to the major changes described above for this release, the following significant changes for the agent are also worth calling out specifically:

 * The `pbench-fio` bench script now requires `fio-3.21` or later; see 5048a149

   * You can find a [Fedora COPR](https://copr.fedorainfracloud.org/coprs/portante/pbench/) build of `fio-3.21-6.pbench` for EPEL 7 & 8

 * [_**DEPRECATED**_] The `pbench-cleanup` utility command is deprecated, and will be removed in a subsequent release (see PR #1828)

 * The release takes in the latest code from stockpile, including support for GPU data collection via the [Nvidia SMI](https://github.com/cloud-bulldozer/stockpile/tree/master/roles/nvidia_smi) role

 * The new `dcgm` tool requires Python 2, an Nvidia based install which might conflict with the Pbench Agent's Python 3 operational requirement in some cases

Server
====
Initial support for moving results to the pbench-server via HTTP `PUT` operations.

Web Server
====
There are no changes and no new `web-server` RPMs have been produced.

Pbench Dashboard
====
The development of the dashboard is not tracked in these release notes. The dashboard has been moved into its own [git repo](https://github.com/distributed-system-analysis/pbench-dashboard).

ChangeLog
====
This is the list of visible commits since the [v0.69.3-agent](https://github.com/distributed-system-analysis/pbench/releases/tag/v0.69.3-agent) release:

a7d1f0d6 `Add 'v0.70.0-beta' release notes`
46aa2add `Update the development image we use for 'b0.70'`
8ae13674 `Add missing 'net-tools' req agent RPM`
8b7424ac `Remove colorlog; add Makefile for pbench-devel`
e7024573 `Rework pass-thru API implementation a bit`
6dc6e4fa `Jenkins integration using Fedora 32 container`
e927f024 `Fix the flaky util-scripts test-51 & test-52`
dd1c52d6 `Address common logging between agent and server`
a37b40c3 `Fix agent side 'test_move_results'`
54b65229 `Use '_pbench_' prefixed env var for host names`
03c14b40 `Make sure we explicitly ask for the full hostname`
50c301d3 `Refactor base to extract unit test overrides`
1261d6db `Address some undesirable tox behaviors`
af520f22 `Fix misaligned deps in tox.ini`
f0f6217c `Direct 'black' to ignore '.git' subtree`
589caa6a `Cleanup 'datalog/prometheus-metrics-datalog'`
ea581356 `Rejig functional unit tests`
aaef93a2 `Fix warning while running unit tests`
1496c7c7 `Remove colorlog`
16099125 `Only do git submodule init at the top of the tree`
98f42b7d `Remove wayward py3-functional unit test`
cb93ab3f `Add ability to tag agent images with beta and alpha`
f28c7a3a `Require pyesbulk 1.0.0 for now`
0c05fb89 `Remove SCL from the agent side`
4eb6d198 `Remove SCL reference in the server trampoline code`
98d50ce5 `Fix the README to restore working URLs`
e3e893f8 `Enhance agent container builds`
7dd58f0b `Add required package name for vmstat`
a4316361 `Remove use of 'screen' from Tool Meister`
5671ea54 `Stop invoking screen directly in unit tests`
1a1dfb73 `Source agent 'base' for remote tool meisters`
b37ae979 `Record the pip3 command output to a log file`
6977291b `Add warning for left-over 'id_rsa' file`
ad6e9de8 `Encapsulate building the final requirements files`
8c7cadfb `Don't '%ghost' 'id_rsa'; only 'rm' in '%postun'`
afa583a7 `Move to rh-python38 for RHEL 7 & use python RPMs`
9574bf60 `Add redis and python3-redis agent RPM requires`
3241acbf `Add a "common" unit test environment`
6d443419 `Move md5sum() method to common utils`
fa6b25de `Don't remove 'id_rsa' and 'pbench-agent.cfg' when uninstalling`
e1ca5f3d `Remove blanket executable file permissions`
b722ecc8 `Use the %config for the agent config file`
3612c003 `Ensure proper use of rh-python36 only for RHEL 7`
c4d68483 `Remove pbench-agent RPM dependencies for tools`
d72f8294 `Update minimum supported Fedora to 31`
92d03835 `Update pbench-agent spec file summary & desc`
8458a450 `Add use of 'rpmlint' on '.spec' files`
5b425b43 `DRY out run-unittests, adding one for the server`
f9087125 `Create the notion of a utils directory`
d4386635 `First pass at a container image for the pbench-server`
fdda1380 `Making a server RPM (without SCL)`
720e6c37 `Initial pbench-agent container image layering`
20a307e9 `RPM making for pbench-agent`
3aa69d65 `General method of fetching git commit ID`
59d1989e `update agent cli to reflect server upload PUT changes`
3526a76a `Additional changes to break up testing requirements`
80c4b7e2 `Break up agent & server requirements`
c29f7caa `Resolves logging error in pbench-server-prep-shim`
ed39d86c `Fix missing space in sosreport --quiet option`
f32e0fdd `write md5sum of a tarfile on disk on server and add upload POST to upload PUT`
7d122d20 `Fix pbench-clear-tools based on new unit tests`
736bd273 `Fix handling of expected exit status in unit tests`
b03cddd2 `Remove , add periods in pbench-clear-tools`
2b8df4db `give pbench user access to /run/pbench-server directory`
20214846 `Deprecate pbench-cleanup & add tests for clear-results`
3d0d1f40 `Switch legacy unit tests to use C.UTF-8 locale`
79086b46 `Updated benchmarks wit init/end`
f72e16eb `Add unit tests for filesize_bytes`
52e0f970 `Reformat the upload api test and fix stored md5sum of log.tar.xz`
c32596fc `Fix util-scripts test-53`
33ee3191 `Post-Merge Review Changes (#1839)`
8bca118c `Prevent server unit test 'test-25' from failing`
ae03d28e `Fix generation of sosreport command`
a27edb09 `Ensure Tool Data Sink internal server object exists`
96633305 `Tell pbr to stop creating AUTHORS & ChangeLog`
276df1ab `Fix bad printf statement in server/test-find-behavior`
d10ab00f `Add missing quote`
f66e8e57 `Early prep for the 0.70 release`
4775f1d8 `Add gunicorn wsgi server configuration`
9c29bc03 `Added DCGM Tool to pbench-agent (keshavm02)`
cb3434e8 `Prometheus/Node_Exporter Full V1 Integration Commit`
a6c5890b `Sort modules in *requirements.txt`
637c4f3b `Lock in use of Perl 5.30+ for Travis CI`
0e7f7069 `Setup base class`
20bfd2b9 `Pbench-server API improvements`
30d2246c `Pbench Server API`
c0e93802 `Clean up the sosreport version number checking`
ed6d8046 `Record the sosreport command that was used`
4f5e6ee5 `Fix bench/util-scripts unit tests env overrides`
ac69d660 `Perhaps useful script for updating gold files`
d32a0913 `Switch indexer.py to pyesbulk package`
64bcdbb2 `Minimal attempt to remove tool meister commands`
01d17fce `Only emit a warning message on missing debugfs`
4ee7dd9c `Fix tool argument handling`
61da5dca `Tweak tool meister tests to use multiple tool opts`
94e42e5a `Ansible role for systemd service`
b5a48712 `Fixes to the systemd service file plus a service file for RHEL7`
ad9eb15d `Make shell.py into a package that exports a main().`
4222d0f5 `A few more cleanups`
d4c6a440 `Make all non-environment variables local to functions named _pbench*`
23cc097e `First pass implementation of the "Tool Meister"`
d8f835dd `Prepare roles for Ansible Galaxy`
991ad99d `Set backup cron job frequency to every minute`
1fae0713 `Make spelling of commit_id consistent`
16432052 `Fixes issue #1668`
d382a8da `Lock versions of flake8 and black to known-good (#1768)`
80c8d8e2 `Give default values to most of the variables.`
5048a149 `Require fio 3.21 and later`
98beb108 `Fix uperf "rr" (round-robin) test XML`
2561f44b `Rename pbench-agent.cfg.example to pbench-agent.cfg`
b8cb2b81 `Avoid hardcoded tools location on bench-scripts`
68157435 `pbench-server-prep-shim-002 into python program`
dbfb7f7e `Fix project name to Pbench.`
c3002f16 `Fix tabs vs spaces in agent/base`
ff58abbb `Fix formatting of contribution guide`
0180aad7 `Use Python 3's pathlib where possible`
bf382c23 `Fix datalog-cpuacct directory order`
47edfa80 `Sort the output of pbench-cull-unpacked-tarballs.py`
500a7371 `Change ToC 'parent' field to "keyword"`
8a00fe15 `Get rid of sudo requirement`
4a06bd46 `Refactoring to introduce PbenchAgentConfig class`
5b3874a5 `Implement PbenchConfig base class`
f9ae8a84 `Move server side logging to common`
c2661dcb `Run agent side test directories individually`
d142d16d `Remove explicit sub-classing of 'object'`
2ee00fcb `Change pbench-dbench to stop using /tmp`
9d428afa `Add py3-functional to run-unittests`
b07c678c `Restructure pbench namespace`
127eb7c0 `Add config options and debug options for agent`
77fa536d `Refactor pbench-cli`
d44f0b59 `Centralize agent results classes`
b8958d31 `Centralize click options`
3e9b9c6a `Search for agent configuration`
a18fc933 `Add unittests`
32d3f285 `Remove getconf.py for server`
59ce3bcd `Remove getconf.py for agent`
e0e65709 `Add pbench-config cli`
c16ada51 `Refactored pbench server and agent code`
af4feecc `Formatted scripts using f-strings`
c1b4e137 `Added script specific and default logging level`
1c91c895 `feat: pbench-server REST API`
6b082d48 `Setup pbench namespace`
