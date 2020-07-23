====================
Structure of results
====================

.. _structure-of-results-1:

Structure of results
====================

Single host
-----------

The single-host case is described in some detail at:
http://pbench.example.com/#sec-12-1.

Here is what a fio run looks like (with most of the files and
lower-level subdirs elided):

::

   .
   |-- fio__2014-11-12_13:17:24
   |   |-- 1-read-4KiB
   |   |   |-- fio.cmd
   |   |   |-- fio.job
   |   |   |-- result.txt
   |   |   |-- sysinfo
   |   |   |   |   ....
   |   |   |   |-- lstopo.txt
   |   |   |   |-- sosreport-a.foo.example.com-pbench-20141112131825.tar.xz
   |   |   |   `-- sosreport-a.foo.example.com-pbench-20141112131825.tar.xz.md5
   |   |   `-- tools-default
   |   |       |-- cmds
   |   |       |   |-- iostat.cmd
   |   |       |   |-- pbench-iostat-postprocess.cmd
   |   |       |   |-- pbench-iostat-postprocess-output.txt
   |   |       |   |-- pbench-iostat-start.cmd
   |   |       |   |-- pbench-iostat-stop.cmd
   |   |       |   |-- ... similar entries for the other tools
   |   |       |   `-- sar.cmd
   |   |       |-- iostat
   |   |       |   |-- device_mapper-average.txt
   |   |       |   |-- device_mapper.html
   |   |       |   |-- device_mapper.js
   |   |       |   |-- disk-average.txt
   |   |       |   |-- disk.html
   |   |       |   `-- disk.js
   |   |       |-- iostat.txt
   |   |       |-- ... similar entries for the other tools
   |   |       `-- sar.txt
   |   |-- 2-read-64KiB
   |   |   |-- fio.cmd
   |   |   |-- fio.job
   |   |   |-- result.txt
   |   |   |-- sysinfo
   |   |   |   |-- ...
   |   |   |   |-- lstopo.txt
   |   |   |   |-- sosreport-a.foo.example.com-pbench-20141112131938.tar.xz
   |   |   |   `-- sosreport-a.foo.example.com-pbench-20141112131938.tar.xz.md5
   |   |   `-- tools-default
   |   |       |-- cmds
   |   |       |   |-- iostat.cmd
   |   |       |   |-- pbench-iostat-postprocess.cmd
   |   |       |   |-- pbench-iostat-postprocess-output.txt
   |   |       |   |-- pbench-iostat-start.cmd
   |   |       |   |-- pbench-iostat-stop.cmd
   |   |       |   |-- ...
   |   |       |   `-- sar.cmd
   |   |       |-- iostat
   |   |       |   |-- device_mapper-average.txt
   |   |       |   |-- device_mapper.html
   |   |       |   |-- device_mapper.js
   |   |       |   |-- disk-average.txt
   |   |       |   |-- disk.html
   |   |       |   `-- disk.js
   |   |       |-- iostat.txt
   |   |       |-- ...
   |   |-- 3-read-1024KiB
   |   |   |-- ...
   |   |-- 4-randread-4KiB
   |   |   |-- ...
   |   |-- 5-randread-64KiB
   |   |   |-- ...
   |   |-- 6-randread-1024KiB
   |   |   |-- ...
   |   `-- fio-summary.txt
   |-- pbench.log
   |-- tmp
   `-- tools.default

   140 directories, 1011 files

There are 6 "iterations" and each iteration corresponds to a
subdirectory of the main directory ``fio__<timestamp>``. Each iteration
contains a few files (``fio.cmd``, ``result.txt``, etc.) and two
subdirs: one for sysinfo (including the collected sosreport) and one for
the tools collection data (``tools-$group``). The latter contains a
``cmds`` subdirectory with files describing the various commands used to
start, stop each tool, postprocess its output, as well as the actual
command to run the tool (e.g. ``iostat.cmd``), a file containing the raw
output from the tool (e.g. ``iostat.txt``) and a subdirectory (e.g.
``iostat``) where the data reductions and turning the data into a
d3-compatible JSON format and producing an HTML page happen. The set of
data reductions is tool dependent, but the suffixes are fixes (``.txt``,
``.js`` and ``.html``).

Multiple hosts
--------------

One registers tools on each remote by hand. Assuming that you are
sitting on the host that acts as the orchestrator for the benchmark run
(where one might or might not run tools - in the following I'm assuming
that tools are run on the orchestrator, but skipping the local
``register-tool-set`` would only run tools on the remotes), then one
might proceed as follows:

::

   register-tool-set
   for remote in $remotes ;do
       register-tool-set --remote $remote
   done

   for iter in $iterations ;do
      ts=$(date +....)
      dir=/var/lib/pbench/...

      start-tools --dir=$dir

      <run the benchmark>

      stop-tools --dir= $dir
      postprocess-tools --dir=$dir
   done

where the run directory may be more than a single level below
``/var/lib/pbench`` and may have various components specified through
–config, the "iteration" name (which may also be thought of as the name
of the experiment - that makes more sense in some cases), a timestamp
and anything else that one might think of to disambiguate **this**
experiment from the next one.

The results structure on the orchestrator and on **each** remote is
exactly the same as in the single host case. But in this case,
``postprocess-tools`` pulls the remote data and creates subdirs for each
remote under the sysinfo branch of the local hosts tree and also under
the tools-$group branch. That way, each remote's results are spread over
various subdirs of the local host and the local host is treated
specially. It might make more sense to have a structure like this
instead (exp1 == iter1 etc. if you prefer to think of them as iterations
of a single experiment, rather than as separate experiments):

::

   benchmark__TS/
   |-- benchmark.txt
   |-- exp1
   |   |-- exp1.txt
   |   |-- host1
   |   |   |-- bench.cmd
   |   |   |-- bench.job
   |   |   |-- result.txt
   |   |   |-- sysinfo
   |   |   `-- tools-default
   |   |-- host2
   |   `-- host3
   |-- exp2
   |   |-- exp2.txt
   |   |-- host1
   |   |   |-- bench.cmd
   |   |   |-- bench.job
   |   |   |-- result.txt
   |   |   |-- sysinfo
   |   |   `-- tools-default
   |   |-- host2
   |   `-- host3
   `-- exp3
       |-- exp3.txt
       |-- host1
       |   |-- bench.cmd
       |   |-- bench.job
       |   |-- result.txt
       |   |-- sysinfo
       |   `-- tools-default
       |-- host2
       `-- host3

   18 directories, 13 files

where the hosts are treated symmetrically. Any benchmark data that are
gathered on each host (remote or local) are under the subdirectory for
that host. Benchmark data that are "global" in some sense are under the
"expN" subdirectory, and there might be a summary describing the set of
experiments in the top-level directory.

I think this structure accommodates Archit's and Peter's concerns and is
fairly easy to implement: it only requires simple changes to
postprocess-tools. A thornier problem is the already existing base of
results, but it could be fixed up once and for all with a bit of
scripting (although that remains to be proved).

The question is whether it imposes artificial limits that are going to
get in our way later, but I cannot think of any (although that may be a
lack of imagination on my part).

