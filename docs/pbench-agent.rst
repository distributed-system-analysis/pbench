==================
Pbench Start Guide
==================

WARNING
=======

This document may describe some future capabilities of pbench. We are
working as fast as we can to make the code catch up to the documentation
and vice-versa, but things may not be exactly as described here. If you
find something not working as described here, please let us know: it may
be a bug in the documentation, a bug in the code or a feature that we
want to implement but we haven't quite gotten to yet.

What is ``pbench``?
===================

Pbench is a harness that allows data collection from a variety of tools
while running a benchmark. Pbench has some built-in script that run some
common benchmarks, but the data collection can be run separately as well
with a benchmark that is not built-in to pbench, or a pbench script can
be written for the benchmark. Such contributions are more than welcome!

Quick links
===========

Convenience links for some places of interest (N.B. The results
directory has changed - see *Accessing results on the web* for the
details):

-  `Results directory <http://pbench.example.com/results/>`__.
-  `pbench RPM repo <http://pbench.example.com/repo>`__
-  `Release notes <http://pbench.example.com/doc/RELEASE-NOTES.html>`__

[2015-01-23 Fri] In preparation for moving the incoming directory to
bigger storage, older directories in the pbench incoming area were
archived (tarred/compressed/moved to new area). The list of these
directories can be found `here <./archived-directories.html>`__.

TL;DR version
=============

Here is the minimum set of commands to get from 0 to a crawl:

::

   wget -O /etc/yum.repos.d/pbench.repo http://repohost.example.com/repo/yum.repos.d/pbench.repo
   yum install pbench-agent -y
   . /etc/profile.d/pbench-agent.sh                          # or log out and log back in
   register-tool-set
   user-benchmark -C test1 -- ./your_cmd.sh
   move-results

Visit the `Results directory <http://pbench.example.com/results/>`__ to
see the results: assuming you ran the above on a host named "myhost",
the results will be in its
"myhost/user_benchmark_test1_<yyyy.mm.ddTHH.MM.SS>" subidrectory.

For explanations, and if crawling is not enough, see subsequent
sections.

How to install
==============

Visit

http://repohost.example.com/repo/yum.repos.d

and copy the ``pbench.repo`` file to ``/etc/yum.repos.d`` on the
SUT [1]_. If the SUT consists of multiple hosts, the file (and pbench)
should be installed on **all** of them. Here is a command that you can
execute (as root) on the SUT to accomplish this:

::

   wget -O /etc/yum.repos.d/pbench.repo http://repohost.example.com/repo/yum.repos.d/pbench.repo

Then

::

   yum install pbench-agent

will install the ``pbench`` agent in ``/opt/pbench-agent``. Before you
do anything else, you need to source the file
``/etc/profile.d/pbench-agent.sh``. It sets PATH appropriately and
defines an env variable \_PBENCH_AGENT_CONFIG to point to the default
pbench configuration file (see *Customizing* below). Alternatively,
logging out and logging back in will source the script automatically.

Updating pbench
---------------

Since the package (as well as the benchmark and tools RPMS that are in
the repo) gets updated fairly often, I have found it necessary to clean
the yum cache in order for yum to see the new package, although you
might want to try updating without cleaning the cache first and if yum
reports no packages to update, then try again after cleaning the cache:

::

   yum clean expire-cache
   yum update pbench-agent

If you try the above update and encounter problems (e.g. the pbench
scripts, or the config file, are not found even after you log out and
log back in), then try the following workaround:

::

   yum reinstall pbench-agent

That should reestablish the missing symlink.

The workaround should not be necessary if your currently installed
release is 0.31-95 or later.

In desperate situations, removing the ``pbench-agent`` package and
reinstalling after cleaning the cache should clear up any problems:

::

   yum erase pbench-agent
   yum clean expire-cache
   yum install pbench-agent

If you upgrade to a release later than -102, please also ensure that you
clear out your tools and reregister them after the upgrade: the label
handling has changed. For example:

::

   clear-tools
   register-tool-set --label=ceph-server --remote=my-ceph-server
   register-tool-set --label=kvmhost --remote=my-kvmhost
   register-tool-set --label=kvmguest --remote=my-kvmguest

First steps
===========

All of the commands take a ``--help`` option and produce a terse usage
message.

The default set of tools for data collection can be enabled with

::

   register-tool-set

You can then run a built-in benchmark by invoking its pbench script -
pbench will install the benchmark if necessary [2]_:

::

   pbench_fio

When the benchmark finishes, the tools will be stopped as well. The
results can be collected and shipped to the standard storage
location [3]_ with

::

   move-results

or

::

   copy-results

First steps with user-benchmark
-------------------------------

If you want to run something that is not already packaged up as a
benchmark script, you may be able to use the ``user-benchmark`` script:
it takes a command as argument, starts the collection tools, invokes the
command, stops the collection tools and postprocesses the results. So
the workflow becomes:

::

   register-tool-set
   user-benchmark --config=foo -- myscript.sh
   move-results

See for host in $hosts ;do register-tool-set --remote=$host done user-benchmark --config=foo -- myscript.sh move-results 

Apart from having to register the collection tools on **all** the hosts,
the rest is the same: ``user-benchmark`` will start the collection tools
on all the hosts, run ``myscript.sh``, stop the tools and run the
postprocessing phase, gathering up all the remote results to the local
host (the local host may be just a controller, not running any
collection tools itself, or it may be part of the set of hosts where the
benchmark is run, with collection tools running).

The underlying assumption is that ``myscript.sh`` will run your
benchmark on all the relevant hosts and will copy all the results into
the standard directory which postprocessing will copy over to the
controller host. ``user-benchmark`` calls the script in its command-line
arguments (everything after the – is just execed by user-benchmark) and
redirects its ``stdout`` to a file in that directory:
``$benchmark_run_dir/result.txt``.

Defaults
========

The benchmark scripts source the base script
(``/opt/pbench-agent/base``) which sets a bunch of defaults:

::

   pbench_run=/var/lib/pbench
   pbench_log=/var/lib/pbench/pbench.log
   date=`date --utc "+%Y.%m.%dT%H.%M.%S"`
   hostname=`hostname -s`
   results_repo=pbench@pbench.example.com
   results_repo_dir=/pbench/public_html/incoming
   ssh_opts='-o StrictHostKeyChecking=no'

These are now specified in the config file
``/opt/pbench-agent/config/pbench.conf``.

Available tools
===============

The configured default set of tools (what you would get by running
``register-tool-set``) is:

-  sar, iostat, mpstat, pidstat, proc-vmstat, proc-interrupts, perf

In addition, there are tools that can be added to the default set with
``register-tool``:

-  blktrace, cpuacct, dm-cache, docker, kvmstat, kvmtrace, lockstat,
   numastat, perf, porc-sched_debug, proc-vmstat, qemu-migrate, rabbit,
   strace, sysfs, systemtap, tcpdump, turbostat, virsh-migrate, vmstat

There is a ``default`` group of tools (that's what ``register-tool-set``
uses), but tools can be registered in other groups using the ``--group``
option of ``register-tool``. The group can then be started and stopped
using ``start-tools`` and ``stop-tools`` using their ``--group`` option.

Additional tools can be registered:

::

   register-tool --name blktrace

or unregistered (e.g. some people prefer to run without perf):

::

   unregister-tool --name perf

Note that perf is run in a "low overhead" mode with options "record -a
–freq=100", but if you want to run it differently, you can always
unregister it and register it again with different options:

::

   unregister --name=perf
   register-tool --name=perf -- --record-opts="record -a --freq=200"

Tools can be also be registered, started and stopped on remote hosts
(see the ``--remote`` option described in Running pbench collection tools with an arbitrary benchmark below for more on this)

Note that in many of these scripts the default tool group is hard-wired:
if you want them to run a different tool group, you need to edit the
script [5]_.

Utility scripts
===============

This section is needed as preparation for the *Second steps* section
below.

Pbench uses a bunch of utility scripts to do common operations. There is
a common set of options for some of these: ``--name`` to specify a tool,
``--group`` to specify a tool group, ``--with-options`` to list or pass
options to a tool, ``--remote`` to operate on a remote host (see entries
in the *FAQ* section below for more details on these options).

The first set is for registering and unregistering tools and getting
some information about them:

``list-tools``
   list the tools in the default group or in the specified group; with
   the –name option, list the groups that the named tool is in. TBD: how
   do you list **all** available tools whether in a group or not?
``register-tool-set``
   call ``register-tool`` on each tool in the default list.
``register-tool``
   add a tool to a tool group (possibly remotely).
``unregister-tool``
   remove a tool from a tool group (possibly remotely).
``clear-tools``
   remove a tool or all tools from a specified tool group (including
   remotely).

The second set is for controlling the running of tools – ``start-tools``
and ``stop-tools``, as well as ``postprocess-tools`` below, take
``--group``, ``--dir`` and ``--iteration`` options: which group of tools
to start/stop/postprocess, which directory to use to stash results and a
label to apply to this set of results. ``kill-tools`` is used to make
sure that all running tools are stopped: having a bunch of tools from
earlier runs still running has been know to happen and is the cause of
many problems (slowdowns in particular):

``start-tools``
   start a group of tools, stashing the results in the directory
   specified by ``--dir``.
``stop-tools``
   stop a group of tools.
``kill-tools``
   make sure that no tools are running to pollute the environment.

The third set is for handling the results and doing cleanup:

``postprocess-tools``
   run all the relevant postprocessing scripts on the tool output - this
   step also gathers up tool output from remote hosts to the local host
   in preparation for copying it to the results repository.
``clear-results``
   start with a clean slate.
``copy-results``
   copy results to the results repo.
``move-results``
   move the results to the results repo and delete them from the local
   host.
``edit-prefix``
   change the directory structure of the results (see the *Accessing
   results on the web* section below for details).
``cleanup``
   clean up the pbench run directory - after this step, you will need to
   register any tools again.

``register-tool-set``, ``register-tool`` and ``unregister-tool`` can
also take a ``--remote`` option (see Benchmark scripts options). 

-  Check that the necessary prerequisites are installed and if not,
   install them.
-  Iterate over some set of benchmark characteristics (e.g.
   ``pbench_fio`` iterates over a couple test types: read, randread and
   a bunch of block sizes), with each iteration doing the following:

   -  create a benchmark_results directory
   -  start the collection tools
   -  run the benchmark
   -  stop the collection tools
   -  postprocess the collection tools data

The tools are started with an invocation of ``start-tools`` like this:

::

   start-tools --group=$group --iteration=$iteration --dir=$benchmark_tools_dir

where the group is usually "default" but can be changed to taste as
described above, iteration is a benchmark-specific tag that
disambiguates the separate iterations in a run (e.g. for ``pbench_fio``
it is a combination of a count, the test type, the block size and a
device name), and the benchmark_tools_dir specifies where the collection
results are going to end up (see the *Results structure* section for
much more detail on this).

The stop invocation is exactly parallel, as is the postprocessing
invocation:

::

   stop-tools --group=$group --iteration=$iteration --dir=$benchmark_tools_dir
   postprocess-tools --group=$group --iteration=$iteration --dir=$benchmark_tools_dir

Benchmark scripts options
-------------------------

Generally speaking, benchmark scripts do not take any pbench-specific
options except ``--config`` (see register-tool --name=blktrace [--remote=foo] -- --devices=/dev/sda,/dev/sdb 

There is no default and leaving it empty causes errors in
postprocessing (this should be flagged).

Utility script options
----------------------

Note that ``move-results``, ``copy-results`` and ``clear-results``
always assume that the run directory is the default ``/var/lib/pbench``.

``move-results`` and ``copy-results`` now (starting with pbench version
0.31-108gf016ed6) take a ``--prefix`` option. This is explained in the
*Accessing results on the web* section below.

Note also that ``start/stop/postprocess-tools`` **must** be called with
exactly the same arguments. The built-in benchmark scripts do that
already, but if you go your own way, make sure to follow this dictum.

``--dir``
   specify the run directory for all the collections tools. This
   argument **must** be used by ``start/stop/postrprocess-tools``, so
   that all the results files are in known places:

   ::

      start-tools --dir=/var/lib/pbench/foo
      stop-tools  --dir=/var/lib/pbench/foo
      postprocess-tools --dir=/var/lib/pbench/foo

``--remote``
   specify a remote host on which a collection tools (or set of
   collection tools) is to be registered:

   ::

      register-tool --name=<tool> --remote=<host>

Running pbench collection tools with an arbitrary benchmark
===========================================================

If you want to take advantage of pbench's data collection and other
goodies, but your benchmark is not part of the set above (see
[[*Available benchmark scripts][Available benchmark scripts]]), or you
want to run it differently so that the pre-packaged script does not work
for you, that's no problem (but, if possible, heed the *WARNING* above).
The various pbench phases can be run separately and you can fit your
benchmark into the appropriate slot:

::

   group=default
   benchmark_tools_dir=TBD

   register-tool-set --group=$group
   start-tools --group=$group --iteration=$iteration --dir=$benchmark_tools_dir
   <run your benchmark>
   stop-tools --group=$group --iteration=$iteration --dir=$benchmark_tools_dir
   postprocess-tools --group=$group --iteration=$iteration --dir=$benchmark_tools_dir
   copy-results

Often, multiple experiments (or "iterations") are run as part of a
single run. The modified flow then looks like this:

::

   group=default
   experiments="exp1 exp2 exp3"
   benchmark_tools_dir=TBD

   register-tool-set --group=$group
   for exp in $experiments ;do
       start-tools --group=$group --iteration=$exp
       <run the experiment>
       stop-tools --group=$group --iteration=$exp
       postprocess-tools --group=$group --iteration=$exp
   done
   copy-results

Alternatively, you may be able to use the ``user-benchmark`` script as
follows:

::

   user-benchmark --config="specjbb2005-4-JVMs" -- my_benchmark.sh

which is going to run ``my_benchmark.sh`` in the
``<run your benchmark>`` slot above. Iterations and such are your
responsibility.

``user-benchmark`` can also be used for a somewhat more specialized
scenario: sometimes you just want to run the collection tools for a
short time while your benchmark is running to get an idea of how the
system looks. The idea here is to use ``user-benchmark`` to run a sleep
of the appropriate duration in parallel with your benchmark:

::

   user-benchmark --config="specjbb2005-4-JVMs" -- sleep 10

will start data collection, sleep for 10 seconds, then stop data
collection and gather up the results. The config argument is a tag to
distinguish this data collection from any other: you will probably want
to make sure it's unique.

This works well for one-off scenarios, but for repeated usage on well
defined phase changes you might want to investigate *Triggers*.

Remote hosts
============

Note that from latest version onwards, we would like to have a file at
http://pbench.example.com/pbench-archive-host where the FQDN of the
pbench web-server lies and the results would be pushed here. Currently
it is ``archivehost.example.com``. This would mean, if in future, we
would like to change the central server settings, we wouldn't want the
users to upgrade to a latest version of pbench. Rather, just change the
FQDN in this hosted file and then new results would automatically be
pushed to the updated location.

Multihost benchmarks
--------------------

Usually, a multihost benchmark is run using a host that acts as the
"controller" of the run. There is a set of hosts on which data
collection is to be performed while the benchmark is running. The
controller may or may not be itself part of that set. In what follows,
we assume that the controller has password-less ssh access to the
relevant hosts.

The recommended way to run your workload is to use the generic
``user-benchmark`` script. The workflow in that case is:

-  Register the collection tools on **each** host in the set:

::

   for host in $hosts ;do
       register-tool-set --remote=$host

-  Invoke ``user-benchmark`` with your workload generator as argument:
   that will start the collection tools on all the hosts and then run
   your workload generator; when that finished, it will stop the
   collection tools on all the hosts and then run the postprocessing
   phase which will gather the data from all the remote hosts and run
   the postprocessing tools on everything.
-  Run ``copy-results`` or ``move-results`` to upload the data to the
   results server.

If you cannot use the ``user-benchmark`` script, then the process
becomes more manual. The workflow is:

-  Register the collection tools on **each** host as above.
-  Invoke ``start-tools`` on the controller: that will start data
   collection on all of the remote hosts.
-  Run the workload generator.
-  Invoke ``stop-tools`` on the controller: that will stop data
   collection on all of the remote hosts.
-  Invoke ``postprocess-tools`` on the controller: that will gather all
   the data from the remotes and run the postprocessing tools on all the
   data.
-  Run ``copy-results`` or ``move-results`` to upload the data to the
   results server.

Customizing
===========

Some characteristics [4]_ of pbench are specified in config files and
can be customized by adding your own config file to override the default
settings.

TBD

Best practices
==============

Clear results
-------------

The ``move-results`` script removes the results directory (assumed to be
within the ``/var/lib/pbench`` hierarchy) after copying it the results
repo. But if there are previous results present (perhaps because
``move-results`` was never invoked, or perhaps because ``copy-results``
was invoked instead), ``move-results`` will copy **all** of them: you
probably do not want that.

It's a good idea in general to invoke ``clear-results``, which cleans
``/var/lib/pbench``, **before** running your benchmark.

Kill tools
----------

If you interrupt a built-in benchmark script (or your own script
perhaps), the collection tools are **not** going to be stopped. If you
don't stop them explicitly, they can severely affect subsequent runs
that you make. So it is strongly recommended that you invoke
``kill-tools`` before you start your run:

::

   kill-tools --group=$group

Clear tools
-----------

This tool will delete the tools.$group file on the local host as well as
on all the remote hosts specified therein. After doing that, you will
need to re-register all the tools that you want to use. In combination
with ``clear-results``, this tool creates a blank slate where you can
start from scratch. You probably don't want to call this much, but it
may be useful in certain isolated cases.

Register tools
--------------

Some tools have **required** options [9]_ and you **have** to specify
them when you register the tool. One example is the ``blktrace`` tool
which requires a ``--devices=/dev/sda,dev/sdb=`` argument.
``register-tool-set`` knows about such options for the default set of
tools, but with other tools, you are on your own.

The trouble is that registration does not invoke the tool and does not
know what options are required. So the best thing to do is invoke the
tool with ``--help``: the ``--help`` option may or may not be recognized
by any particular tool, but either way you should get a usage message
that labels required options. You can then register the tool by using an
invocation similar to:

::

   register-tool --name=blktrace -- --devices=/dev/sda,/dev/sdb

Using ``--dir``
---------------

If you use the tool scripts explicitly, specify
``--dir=/var/lib/pbench/<run-id>`` so that all the data are collected in
the specified directory. Also, save any data that your benchmark
produces inside that directory: that way, ``move-results`` can move
everything to the results warehouse.

Make the ``<run-id>`` as detailed as possible to disambiguate results.
The built-in benchmark scripts use the following form:
``<benchmark>_<config>_<ts>``, e.g

::

   fio_bagl-16-4-ceph_2014.12.15T15.58.51

where the ``<config>`` part (``bagl-16-4-ceph``) comes from the
``--config`` option and can be as detailed as you want to make it.

Using ``--remote``
------------------

If you are running multihost benchmarks, we strongly encourage you to
set up the tool collections using ``--remote``. Choose a driver host
(which might or might not participate in the tool data collection: in
the first case, you register tools locally as well as remotely; in the
second, you just register them remotely) and run everything from it.
During the data collection phase, everything will be pulled off the
remotes and copied to the driver host, so it can be moved to the results
repo as a single unit. Consider also using ``--label`` to label sets of
hosts - see *Using ``--label``* for more information.

Using ``--label``
-----------------

When you register remotes, ``--label`` can be used to give a meaningful
label to the results subdirectories that come from remote hosts. For
example, use =–label=server" (or client, or vm, or capsule or whatever
else is appropriate for your use case).

Results handling
================

Accessing results on the web
----------------------------

This section describes how to get to your results using a web browser.
It describes how ``move-results`` moves the results from your local
controller to a centralized location and what happens there. It also
describes the ``--prefix`` option to ``move-results`` (and
``copy-results``) and a utility script, ``edit-prefix``, that allows you
to change how the results are viewed.

N.B. This section applies to the pbench RPM version 0.31-108gf016ed6 and
later. If you are using an earlier version, please upgrade at your
earliest convenience.

Where to go to see results
~~~~~~~~~~~~~~~~~~~~~~~~~~

The canonical place is

http://resultshost.example.com/results/

There are subdirectories there for each controller host (the host on
which ``move-results`` was executed) and underneath those, there are
subdirectories for each pbench run.

The leaves of the hierarchy are actually symlinks that point to the
corresponding results directory in the old, flat ``incoming/``
hierarchy. Direct access to ``incoming/`` is now deprecated (and will
eventually go away).

The advantage is that the ``results/`` hierarchy can be manipulated to
change one's view of the results [10]_, while leaving the ``incoming/``
hierarchy intact, so that tools manipulating it can assume a fixed
structure.

In the interim, a simple script is running once an hour creating any
missing links from ``results/`` to ``incoming/``. It will be turned off
eventually after everybody has upgraded to this or a later version of
pbench.

``move-results`` and its ``--prefix`` option
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to make ``move-results`` more robust, it now packages up the
results in a tarball, computes an MD5 checksum, copies the tarball to an
archive area, checks that the MD5 checksum is still correct and **then**
deletes the results from one's local host.

The tarball is unpacked into the ``incoming/`` hierarchy by a cron
script which runs every minute (so there might be a short delay before
the results are available), and plants a symlink to the results
directory in the ``results/`` hierarchy.

Using the ``--prefix=`` option to ``move-results`` affects where that
symlink is planted (and that's the only thing it affects). For example,
if your controller host is ``alphaville`` and the results name is
``fio__2015.03.30T13.33.15``, normally ``move-results`` would unpack the
tarball under ``incoming/alphaville/fio__2015.03.30T13.33.15`` and plant
a symlink pointing to that at
``results/alphaville/fio__2015.03.30T13.33.15``. But if you wanted to
group all your fio results under ``results/alphaville/fio``, you could
instead say

::

   move-results --prefix=fio

which would plant the link at
``results/alphaville/fio/fio__2015.03.30T13.33.15`` instead of planting
it at ``results/alphaville/fio__2015.03.30T13.33.15``.

``edit-prefix``
~~~~~~~~~~~~~~~

What if you forget to use ``--prefix`` when calling ``move-prefix``? Or
you want to reorganize further, perhaps pushing a set of results further
down in the ``results/`` hierarchy?

You can do that with ``edit-prefix``. For example, continuing the
example above, suppose you want to push a bunch of results from ``fio/``
down another level, perhaps to group all the fio results on a particular
platform together:

::

   edit-prefix --prefix=fio/dl980 fio/fio__2015.03.30T13.33.15 ...

would do that. The arguments **must** exist in the appropriate place in
the ``results`` hierarchy and the symlink at the leaf **must** point to
an existing result in the ``incoming/`` hierarchy. The links are then
moved, using the new prefix, to a different place in the ``results/``
hierarchy.

``edit-prefix`` works similarly to ``move-results``: it sends
instruction to the centralized results repository which are executed by
a cron script running once a minute; so it may take a bit before the
change takes effect.

Normalized directory structure
------------------------------

Andrew writes:

   -  All of the benchmark scripts use
      *var/lib/pbench/$benchmark-$config-$date/$iteration/reference-result/tools-$tool_group*
   -  This allows for 1-N iterations and 1-N samples per iteration. For
      example, user-benchmark uses
      *var/lib/pbench/user-benchmark-$config-$date/1/reference-result*

-  A self-explanatory example of the above mentioned hierarchical
   pattern is as follows:

::

   fio__2015.01.15T19.45.10/ --> $benchmark-$config-$date
   ├── 1-read-4KiB  --> $iteration
   │   └── reference-result --> reference-result/
   │       │  
   │       └── tools-default --> tools-$tool_group/
   │           ├── cmds
   │           ├── iostat
   │           ├── mpstat
   │           ├── perf
   │           ├── pidstat
   │           ├── proc-interrupts
   │           ├── proc-vmstat
   │           ├── sar
   │           └── turbostat

``reference-results``
   This is calculated (based on standard deviation) as the best result
   from all the iterations, after the tests have ended. This is just a
   sym-link to one of the iterations, so as to make it easier for the
   user take a quick look at the results.

CSV
---

Postprocessing now produces CSV files of the results. Each row consists
of a timestamp and a series of measures. The first row is a header row
with the labels.

The CSV files are directly used by the Javascript library that allows
users to view graphs. The library runs in the client browser and pulls
the CSV file from the server. If that file is large, there might be a
substantial delay in the rendering of the graphs. In certain cases,
large files have caused browsers to explode. The only known method to
avoid that currently is to reduce the sampling frequency and therefore
make the files smaller. This is unsatisfactory and we are working to
mitigate this problem

Results structure
-----------------

Local results structure
~~~~~~~~~~~~~~~~~~~~~~~

Andrew writes:

   To understand how data is arranged, you have to understand the
   different requirements users & benchmarks might have:

   The simplest use case is when a user just wants to get tool data for
   a single measurement. For example, a user may run:

   ::

      register-tool-set
      dir=/var/lib/pbench/mytest
      start-tools --dir=$dir
      my-benchmark-script.sh
      stop-tools --dir=$dir
      postprocess-tools --dir=$dir
      move-results

   (the "my-benchmark-script.sh" above could be substituted by simply
   waiting until whatever thing is happening is done, or a "sleep <x>",
   etc)

   The hierarchy is then pretty simple: ``/var/lib/pbench/my-test`` is
   the base directory for this test, and the tool data is in
   ``tools-$tool_group``. Since they used the default tool group (they
   did not specify an alternative), it's "tools-default". The base
   directory is where a user should put any data regarding the workload
   (benchmark result). So, in general, when processing a test result,
   the benchmark data is in ./mytest, and the tool data for this
   benchmark is in ./mytest/tools-$tool_group/. These two are always
   tightly coupled to ensure the tool data is always included in the
   benchmark result.

   In the case above, the user has total control over the –dir name. The
   "tools-default" is a fixed name, which originates from
   "tools-$tool_group". This should not change. "./<dir>/tools-*" should
   always be recognizable by other postprocessing scripts as the tools
   data for test <dir>. If a user wants to identify this result
   uniquely, the upper directory should be used, for example:

   a first test:

   ::

      dir=/var/lib/pbench/mytest-using-containers
      start-tools --dir=$dir
      my-benchmark-script.sh --use-docker
      stop-tools --dir=$dir
      postprocess-tools --dir=$dir
      move-results

   and then a second test:

   ::


      dir=/var/lib/pbench/mytest-using-VMs
       start-tools --dir=$dir
       my-benchmark-script.sh --use-vms
       stop-tools --dir=$dir
       postprocess-tools --dir=$dir
       move-results

   When a user uses a built-in pbench benchmark, the directory hierarchy
   is maintained [and optionally expanded], but some of the directory
   names (or rather a portion of the name) is under the control of the
   pbench benchmark script. This is to maintain consistency across the
   pbench benchmark scripts. The pbench benchmark scripts should include
   a date in the base directory name and include contents from the
   –config option.

   Since many benchmarks actually have several measurements, an extra
   level of directory is added to accommodate this. Instead of
   /var/lib/pbench/<mytest>/tools-default, we usually end up with
   /var/lib/pbench/<mytest>/<test-iteration[s]>/tools-default.

   There are actually multiple reasons for the ./<test-iteration[s]>/
   addition, as there are many reasons to have more than one test
   execution for any given benchmark. These include (but are not limited
   to):

   #. a benchmark simply has multiple **different** tests.
   #. a pbench benchmark script often tries to execute several benchmark
      configurations, varying things like load levels & different
      benchmark options, so the user does not have script these
      themselves.
   #. benchmarks may need multiple samples of the exact same benchmark
      configuration to compute standard deviation.

   An example of (1) is SPECcpu, where there are several completely
   different tests, and they each should get their own result
   sub-directory (./<test-iteration-X/), with its own tools-$tool_group
   subdirectory. The "main" directory (/var/lib/pbench/<mytest>)
   includes the overall result, and generally where any report generated
   would reside.

   An example of (2) is uperf, where by default this script runs several
   configurations, varying message size, number of instances, and
   protocol type. This can produce dozens of different results, all of
   which need to be organized properly. Each unique configuration uses a
   unique ./<iteration>/ directory under the main directory, each with
   their own tools-$tool_group subdir.

   An example of (3) is dbench, where by default 5 samples of the same
   test are taken, Each of these results are kept in a ./<iteration>/
   subdir. After the end of the tests, the dbench script computes the
   standard deviation and even creates a symlink, "reference-result", to
   the 1 iteration-dir that it's result closest to the sdtdev.

   More than one of these uses for iterations can also be used. In fact,
   uperf, uses iterations for both varying benchmark options (like
   message sizes), but for each of those unique configurations, multiple
   samples are taken to compute a standard deviation. This then involves
   two levels of subdirs for the iterations. So, in this case, we have a
   hierarchy like:

   ::

      /var/lib/pbench/<my-test>
      /var/lib/pbench/<my-test>/1-tcp-stream-1024k-1instance/
      /var/lib/pbench/<my-test>/1-tcp-stream-1024k-1instance/sample1/

   So, in summary:

   #. tool data is always in a subdir of where the benchmark result is
      kept. The tool subdir starts with "tools-"

   #. A benchmark result dir can be as high up as
      *var/lib/pbench/<mytest>*, or it can be 1 or two levels deeper,
      depending on the need for multiple test runs. Some kind of
      benchmark summary should always be in /var/lib/pbench/<mytest>.

   I will cover remote tools in another comment section.

Remote results structure
~~~~~~~~~~~~~~~~~~~~~~~~

When pbench tools are registered remotely, the structure described above
is followed on each host

Post-processing collects all the remote results locally. The results
from each remote host are pushed down one level in the hierarchy, with
the name of the host (augmented by the value of the ``--label`` option
if applicable) providing the extra directory level at the top.

In addition, if local results are present, they are also pushed down one
level in the hierarchy with the name of the local host providing the
extra directory level at the top (this happens in the purely local case
as well, for uniformity's sake). Again, the value of the ``--label``
option is used to augment the name if applicable.

Advanced topics
===============

Triggers
--------

Triggers are groups of tools that are started and stopped on specific
events. They are registered with ``register-tool-trigger`` using the
``--start-trigger`` and ``--stop-trigger`` options. The output of the
benchmark is piped into the ``tool-trigger`` tool which detects the
conditions for starting and stopping the specified group of tools.

There are some commands specifically for triggers:

``register-tool-trigger``
   register start and stop triggers for a tool group.
``list-triggers``
   list triggers and their start/stop criteria.
``tool-trigger``
   this is a Perl script that looks for the start-trigger and
   end-trigger markers in the benchmark's output, starting and stopping
   the appropriate group of tools when it finds the corresponding
   marker.

As an example, ``pbench_dbench`` uses three groups of tools: warmup,
measurement and cleanup. It registers these groups as triggers using

::

   register-tool-trigger --group=warmup --start-trigger="warmup" --stop-trigger="execute"
   register-tool-trigger --group=measurement --start-trigger="execute" --stop-trigger="cleanup"
   register-tool-trigger --group=cleanup --start-trigger="cleanup" --stop-trigger="Operation"

It then pipes the output of the benchmark into ``tool-trigger``:

::

   $benchmark_bin --machine-readable --directory=$dir --timelimit=$runtime
                  --warmup=$warmup --loadfile $loadfile $client |
                  tee $benchmark_results_dir/result.txt |
                  tool-trigger "$iteration" "$benchmark_results_dir" no

``tool-trigger`` will then start the warmup group when it encounters the
string "warmup" in the benchmark's output and stop it when it encounters
"execute". It will also start the measurement group when it encounters
"execute" and stop it when it encounters "cleanup" - and so on.

Obviously, the start/stop conditions will have to be chosen with some
care to ensure correct actions.

FAQ
===

What does ``--name`` do?
------------------------

This option is recognized by ``register-tool`` and ``unregister-tool``:
it specifies the name of the tool that is to be (un)registered.
``list-tools`` with the ``--name`` option list all the groups that
contain the named tool [8]_.

What does ``--config`` do?
--------------------------

This option is recognized by the benchmark scripts (see *Available
benchmark scripts* above) which use it as a tag for the directory where
the benchmark is going to run. The default value is empty. The run
directory for the benchmark is constructed this way:

::

   ${pbench_run}/${benchmark}_${config}_${date}

where ``$pbench_run`` and ``$date`` are set by the
``/opt/pbench-agent/base`` script and ``$benchmark`` is set to the
obvious value by the benchmark script; e.g. a fio run with config=foo
would run in the directory
``/var/lib/pbench/fio_foo_2014.11.10T15.47.04``.

What does ``--dir`` do?
-----------------------

This option is recognized by ``start-tools``, ``stop-tools``,
``tool-trigger`` and ``postprocess-tools``. It specifies the directory
where the tools are going to stash their data. The default value is
``/tmp``. Each group then uses it as a prefix for its own stash, which
has the form ``$dir/tools-$group``. Part of the stash is the set of cmds
to start and stop the tools - they are stored in
``$dir/tools-$group/cmds``. The output of the tool is in
``$dir/tools-$group/$tool.txt``.

This option **has** to be specified identically for each command when
invoking these commands (actually, each of the commands should be
invoked with the identical set of **all** options, not just ``--dir``.)

If you use these tools explicitly (i.e. you don't use one of the
benchmark scripts), it is **highly** recommended that you specify this
option explicitly and not rely on the ``/tmp`` default. For one, you
should make sure that different iterations of your benchmark use a
**different** value for this option, otherwise later results will
overwrite earlier ones.

**N.B.** If you want to run ``move-results`` or ``copy-results`` after
the end of the run, your resuls should be under ``/var/lib/pbench``:
``move/copy-results`` does not know anything about your choice for this
option; it only looks in ``/var/lib/pbench`` for results to upload. So
if you are planning to use ``move/copy-results``, make sure that the
specified directory is a subdirectory of ``/var/lib/pbench``.

What does ``--remote`` do?
--------------------------

pbench can register tools on remote hosts, start them and stop them
remotely and gather up the results from the remote hosts for
post-processing. The model is that one has a controller or orchestrator
and a bunch of remote hosts that participate in the benchmark run.

The pbench setup is as follows: ``register-tool-set`` or
``register-tool`` is called on the controller with the ``--remote``
option, once for each remote host:

::

   for remote in $remotes ;do
       register-tool-set --remote=$remote --label=foo --group=$group
   done

That has two effects: it adds a stanza for the tool to the appropriate
``tools.$group`` file on the remote host and it also adds a stanza like
this to the controller ``tools.$group`` file:

::

   remote@<host>:<label>

The label is optionally specified with ``--label`` and is empty by
default.

When ``start-tools`` is called on the controller, it starts the local
collection (if any), but it also interprets the above stanzas and starts
the appropriate tools on the remote hosts. Similarly for ``stop-tools``
and ``postprocess-tools``.

What does ``--label`` do?
-------------------------

TBD

How to add a collection tool
----------------------------

Tool scripts are mostly boilerplate: they need to take a standard set of
commands (–install, –start, –stop, –postprocess) and a standard set of
options (–iteration, –group, –dir, –interval, –options). Consequently,
the easiest thing to do is to take an existing script and modify it
slightly to call the tool of your choice. I describe here the case of
turbostat.

There are some tools that timestamp each output stanza; there are others
that do not. In the former case, make sure to use whatever option the
tool requires to include such timestamps (e.g. vmstat -t on RHEL6 or
RHEL7 - but strangely **not** on Fedora 20 - will produce such
timestamps).

There are some tools that are included in the default installation -
others need to be installed separately. Turbostat is not always
installed by default, so the tool script installs the package (which is
named differently on RHEL6 and RHEL7) if necessary. In some cases (e.g.
the sysstat tools), we provide an RPM in the pbench repo and the tool
script makes sure to install that if necessary.

The only other knowledge required is where the tool executable resides
(usually /usr/bin/<tool> or /usr/local/bin/<tool> - /usr/bin/turbostat
in this case) and the default options to pass to the tool (which can be
modified by passing –options to the tool script).

So here are the non-boilerplate portions of the
`turbostat <https://github.com/distributed-system-analysis/pbench/tree/tool-scripts/turbostat>`__
tool script. The first interesting part is to set ``tool_bin`` to point
to the binary:

::

   # Defaults
   tool=$script_name
   tool_bin=/usr/bin/$tool

This only works if the script is named the same as the tool, which is
encouraged. If the installed location of your tool is not ``/usr/bin``,
then adjust accordingly.

Since turbostat does not provide a timestamp option, we define a datalog
script to add timestamps (no need for that for vmstat e.g.) and use that
as the tool command:

::

   case "$script_name" in
       turbostat)
       tool_cmd="$script_path/datalog/$tool-datalog $interval $tool_output_file"
       ;;
   esac

The `datalog
script <https://github.com/distributed-system-analysis/pbench/tree/tool-scripts/datalog/turbostat-datalog>`__
uses the ``log-timestamp`` pbench utility to timestamp the output. It
will then be up to the postprocessing script to tease out the data
appropriately.

The last interesting part dispatches on the command - the install is
turbostat-specific, but the rest is boilerplate: ``--start`` just
executes the ``tool_cmd`` as defined above and stashes away the pid, so
that ``--stop`` can kill the command later; ``--postprocess`` calls the
separate post-processing script (see below):

::

   release=$(awk '{x=$7; split(x, a, "."); print a[1];}' /etc/redhat-release)
   case $release in
       6)
           pkg=cpupowerutils
           ;;
       7)
           pkg=kernel-tools
           ;;
       *)
           # better be installed already
           ;;
   esac

   case "$mode" in
       install)
       if [ ! -e $tool_bin ]; then
               yum install $pkg
               echo $script_name is installed
       else
               echo $script_name is installed
       fi
       start)
       mkdir -p $tool_output_dir
       echo "$tool_cmd" >$tool_cmd_file
       debug_log "$script_name: running $tool_cmd"
       $tool_cmd >>"$tool_output_file" & echo $! >$tool_pid_file
       wait
       ;;
       stop)
       pid=`cat "$tool_pid_file"`
       debug_log "stopping $script_name"
       kill $pid && /bin/rm "$tool_pid_file"
       ;;
       postprocess)
       debug_log "postprocessing $script_name"
       $script_path/postprocess/$script_name-postprocess $tool_output_dir
       ;;
   esac

Finally, there is the post-processing tool: the simplest thing to do is
nothing. That's currently the case for the
`turbostat <https://github.com/distributed-system-analysis/pbench/tree/tool-scripts/postprocess/turbostat-postprocess>`__
post-processing tool, but ideally it should produce a JSON file with the
data points and an HTML file that uses the nv3 library to plot the data
graphically in a browser. See the
`postprocess <https://github.com/distributed-system-analysis/pbench/tree/tool-scripts/postprocess>`__
directory for examples, e.g. `the iostat postprocessing
tool <https://github.com/distributed-system-analysis/pbench/tree/tool-scripts/postprocess/iostat-postprocess>`__.

How to add a benchmark
----------------------

TBD

How do I collect data for a short time while my benchmark is running?
---------------------------------------------------------------------

Running

::

   user_benchmark -- sleep 60

will start whatever data collections are specified in the default tool
group, then sleep for 60 seconds. At the end of that period, it will
stop the running collections tools and postprocess the collected data.
Running move-results afterwards will move the results to the results
server as usual.

I have a script to run my benchmark - how do I use it with pbench?
------------------------------------------------------------------

pbench is a set of building blocks, so it allows you to use it in many
different ways, but it also makes certain assumptions which if not
satisfied, lead to problems.

Let's assume that you want to run a number of ``iozone`` experiments,
each with different parameters. Your script probably contains a loop,
running one experiment each time around. If you can change your script
so that it executes **one** experiment specified by an argument, then
the best way is to use the ``user-benchmark`` script:

::

   register-tool-set
   for exp in experiment1 experiment2 experiment3 ;do
       user-benchmark --config $exp -- my-script.sh $exp
   done
   move-results

The results are going to end up in directories named
``/var/lib/pbench/user-benchmark_$exp_$ts`` for each experiment
(unfortunately, the timestamp will be recalculated at the beginning of
each ``user-benchmark`` invocation), before being uploaded to the
results server.

Alternatively, you can modify your script so that each experiment is
wrapped with start/stop/postprocess-tools and then call move-results at
the end:

::

   register-tool-set
   for exp in experiment1 experiment2 experiment3 ;do
       start-tools
       <run the experiment>
       stop-tools
       postprocess-tools
   done
   move-results

Footnotes
=========

.. [1]
   "System under test".

.. [2]
   The current version of pbench-agent yum installs prebuilt RPMs of
   various common benchmarks: dbench, fio, iozone, linpack, smallfile
   and uperf, as well as the most recent version of the sysstat tools.
   We are planning to add more benchmarks to the list: iperf, netperf,
   streams, maybe the phoronix benchmarks. If you want some other
   benchmark (AIM7?), let us know.

.. [3]
   The standard storage location currently is
   http://resultshost.example.com/incoming but it is subject to change
   without notice.

.. [4]
   Only a few such characteristics exist today, but the plan is to move
   more hardwired things into the config files from the scripts. If you
   need to override some setting and have to modify scripts in order to
   do so, let us know: that's a good candidate for the config file.

.. [5]
   That will be handled by a configuration file in the future.

.. [6]
   It is probably better to bundle these options in a configuration
   file, but that's still WIP.

.. [7]
   There is work-in-progress to provide a higher-level interface for this.

.. [8]
   A list of available tools in a specific group can be obtained with
   the ``--group`` option of ``list-tools``; unfortunately, there is no
   option to list all available tools - the current workaround is to
   check the contents of ``/opt/pbench-agent/tool-scripts``.

.. [9]
   Yes, I know: it's an oxymoron.

.. [10]
   E.g. A performance engineer was NFS-mounting the ``incoming/``
   hierarchy, grouping his results under separate subdirectories for
   fio, iozone and smallfile, and grouping them further under
   thematically created subdirectories ("baremetal results for this
   configuration", "virtual host results under that configuration"
   etc.), primarily because having them all in a single directory was
   slow, as well as confusing. There were two problems with this
   approach which motivated the prefix approach described above. One was
   that the NFS export of the FUSE mount of the gluster volume that
   houses the result is extremetly flakey. The other is that the
   ``incoming/`` hierarchy is modified, which makes the writing of tools
   to extract data harder: they have to figure out arbitrary changes,
   instead of being able to assume a fixed structure.

