====================
Configuration
====================

Getting Started
===============

By default, pbench benchmarks collect configuration data of a system,
stored in the sysinfo top level directory of a pbench result, collected
at the beginning and end of a benchmark (with one exception,
pbench-user-benchmark only collects at the end).

The structure of the sysinfo directory in a pbench result, for example,
``/var/lib/pbench-agent/pbench_userbenchmark_example_2019.07.18T12.00.00/``
is given below followed by a brief explanation of each different type of
configuration data.

-  sysinfo
-  end

   -  hostname
   -  block-params.log
   -  config-5.0.17-300.fc30.x86\_64
   -  libvirt/
   -  lstopo.txt
   -  security-mitigation-data.txt
   -  sosreport-localhost-localhost-pbench-2019-06-10-mrqgzbh.tar.xz
   -  sosreport-localhost-localhost-pbench-2019-06-10-mrqgzbh.tar.xz.md5
   -  stockpile.json
   -  stockpile.log

config-[kernel\_version]
------------------------

The file contains kernel configuration data.

The data is collected using
`pbench-sysinfo-dump#L38 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L38>`__.
The script uses ``uname`` system utility (``systemcall`` is a term used
for all the APIs provided by the kernel) to collect kernel release
information and then checks if a corresponding kernel configuration file
exists on the system. If it does, the script simply copies the file,
located in ``/boot`` directory, to the ``sysinfo`` directory.

The file contains data in a key value format where the key is a metric
name and the value can be a string literal or a number. The keys and the
values are separated by an equality sign.

security-mitigation-data.txt
----------------------------

The file contains CPU vulnerabilities data and RHEL-specific flag
settings.

The data is collected using
`pbench-sysinfo-dump#L44 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L44>`__.
The script checks if ``/sys/devices/system/cpu/vulnerabilities``
directory exists. If it does, the script prints the filenames and the
contents of all the files located in the directory. After that, it
repeats the same steps for the ``/sys/kernel/debug/x86`` directory.

The file contains data in a key value format where the key is a file
name and the value is the content of the file.

libvirt/
--------

The directory provides information about libvirt, an open-source API,
daemon and management tool for managing platform virtualization.

The data is collected using
`pbench-sysinfo-dump#L60 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L60>`__.
The script copies libvirt files located at ``/var/log/libvirt`` and
``/etc/libvirt`` directories to the ``sysinfo/libvirt/log`` and
``sysinfo/libvirt/etc`` directories respectively. Only the files whose
name follows the regex ``*.log`` are copied from the
``/var/log/libvirt`` directory.

lstopo.txt
----------

The file provides information about the topology of the system.

The data is collected using
`pbench-sysinfo-dump#L71 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L71>`__.
The script executes the command ``lstopo --of txt`` and dumps its output
into a text file only if ``/usr/bin/lstopo`` file exists on the system.

block-params.log
----------------

The file provides information about block devices.

The data is collected using
`pbench-sysinfo-dump#L79 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L79>`__.
The script loops over all the files which satisfy the regex:
``/sys/block/[s,h,v]d\*[a-z]/`` and prints each file name along with the
contents of the file.

The file contains data in a key value format where the key is the file
name and the value is the content of the file..

sosreport tarball (e.g. sosreport-localhost-localhost-pbench-2019-05-29-rtvzlke.tar.xz)
---------------------------------------------------------------------------------------

The tarball contains system configuration and diagnostic information
collected by invoking the ``sosreport`` command.

The data is collected using
`pbench-sysinfo-dump#L87 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L87>`__.
The script uses ``sosreport`` command with different plugins to get the
required system information. The resulting tarball contains a number of
files copied from the system as well as the output of several commands
executed on the system.

ara
---

This specific file is not in the scope of my internship because ara
works with ``python2`` and Fedora 30, which is installed on my system,
works with ``python3`` only.

stockpile.json
--------------

The file contains system information gathered by the
`stockpile <https://github.com/redhat-performance/stockpile>`__ tool
using Ansible.

The data is collected using
`pbench-sysinfo-dump#L153 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L153>`__.
The script runs a specified stockpile playbook with the given stockpile
options. The stockpile playbook has a number of roles associated with
it, for example, ``ceph``, ``cpu``, etc. for each of which there is a
specific ansible playbook called ``main.yml``, which contains the rules
to collect information related to that role.

The file contains data in a json file format.

insights tarball
----------------

The tarball contains system information gathered by the
`insights-client <https://github.com/RedHatInsights/insights-client>`__.

The data is collected using
`pbench-sysinfo-dump#L189 <https://github.com/distributed-system-analysis/pbench/blob/master/agent/util-scripts/pbench-sysinfo-dump#L189>`__.
The script uses ``insights-client`` command with different options to
get the system information. The resulting tarball contains a number of
files copied from the system as well as the output of several commands
executed on the system.
