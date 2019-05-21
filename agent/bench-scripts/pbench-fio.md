
This page describes how to use pbench-fio to do storage performance testing.  It includes these topics:

* [random](#random-workloads) and [sequential](#sequential-workloads) workload parameters
* [cache dropping](#cache-dropping)
* [when and how](#warming-up-the-system) to ramp up workload
* ensure [persistent writes](#data-persistence)
* [rate limiting](#limiting-IOPS)
* measure [latency percentile change over time](#measuring-latency-percentiles)
* example from [OpenStack Cinder testing](#example-of-openstack-cinder-volumes)

Before we go into the [syntax details](#syntax) of pbench-fio parameters, 
which are different in some cases than the fio input parameters, 
we describe why pbench-fio exists, and how to make use of it.

# overview of usage opportunities and constraints

pbench-fio was created to automate sets of fio tests, 
including calculations of statistics for throughputs and latency.  
The fio benchmark itself does not do this.

pbench-fio also was created with distributed storage performance testing in mind -- 
it uses the **fio --client** option to allow fio to start up a storage performance test 
on a set of hosts simultaneously and collect all the results to a central location.

pbench-fio supports ingestion of these results into a repository, 
such as elastic search, through JSON-formatted results that are easily parsed.
Traditional fio output is very difficult to parse correctly 
and the resulting parser is hard to understand and likely to break as fio evolves over time.

pbench-fio also provides additional postprocessing for the new fio latency histogram logs.   This feature lets you graph latency percentiles cluster-wide as a function of time.  These graphs are really important when you are running very long tests and want to look at variations in latency caused by operational events such as node, disk or network failure/replacement.

# difference between sequential and random workload parameters

Ideally we would like to feed fio one set of test parameters 
and have it churn through all the multiple iterations of each data point, 
collecting and analyzing all the results for us.  That is the dream ;-)

However, here is why this is difficult or even impossible to do:

* applications often do sequential I/O in buffered mode
* applications often do random I/O in unbuffered mode

Unfortunately there is no one set of pbench-fio input parameters 
that lets you run both sequential and random tests with the same set of parameters, so far.

## sequential workloads

Applications typically do unbuffered I/O, 
with write aggregation and read prefetching done at client, using a single thread per file.  
Examples of this are software builds, and image/audio/video processing.  
If you do unbuffered (i.e. O_DIRECT) writes/reads to a sequential file, 
throughput will be extremely slow for small transfer sizes, 
but will not be representative of typical application performance.

## random workloads

High-performance applications sometimes do random I/O in O_DIRECT/O_SYNC mode 
(each write has to make it to storage before being acknowledged), 
using asynchronous I/O such as libaio library provides 
to maintain multiple in-flight I/O requests from a single thread.  
They do this for several reasons:

* avoid prefetching data that will never be used by the application
* avoid network overhead of small writes from the client to the server process

If you do buffered random writes, for example, 
you will queue up a ton of requests but they will not actually get written to disk immediately.  
This situation can result in artificially high IOPS numbers
which do not reflect steady-state performance of an application in this environment.  
There are a couple of ways to solve this problem:

1. run a test that is so large that the amount of buffered data is an insignificant percentage of the total data accessed.
2. run a write test that includes time required to fsync the file descriptors to flush all outstanding writes to block devices.

Both of these options have issues.  
Option 1 increases test time significantly 
depending on the potential amount of buffering taking place in the system. 
Option 2 has the disadvantages that short tests may spend excessive time 
in the fsync call and not in the actual write-related system calls, 
and queue depth is not controlled.

Contrast this with use of **O_DIRECT** or **O_SYNC** reads and writes.  
Here the situation is reversed - we can run a test that uses only a small 
fraction of the total data set and get representative numbers.  
For example, we could use **fallocate()** system call to quickly create files 
that span the entire block device, 
and then randomly read/write only an insignificant fraction of the entire set of files, 
yet still get representative throughput and latency numbers.  
The same is true for using fio for random I/O on block devices.  

## shared filesystems

A slightly different set of parameters is needed for pbench-fio to work with shared filesystems (where same set of files
is shared by multiple clients/mountpoints).  For this to work, you must do 2 things:

* specify --target=my-directory 
* specify --jobfile=/opt/pbench-agent/bench-scripts/templates/fio-shared-fs.job  

**my-directory** is the shared filesystem mountpoint or some subdirectory of it

The job file specification tells fio to target a directory instead of a file.  fio --client
will then generate unique filenames for every pair of (host, job-number) combinations
so that no 2 fio jobs will access the same pathname.  See [fio
documentation](https://fio.readthedocs.io/en/latest/fio_doc.html#client-server) for details.
(at present the combination of numjobs > 1 with fio-shared-fs.job has not been tested)

# data persistence

Performance of writes is usually only interesting if we know that the writes are persistent (will be visible after a client or server abrupt reset (i.e. crash or power-cycle).  Otherwise you may be just writing to RAM.  For sequential writes, this can be accomplished with the fio jobfile parameter **fsync_on_close=1** . For random writes, this can be accomplished with the parameter **--sync=1** .  Technically O_DIRECT open flag does not guarantee persistence of writes, and only specifies that writes bypass buffer cache.  For example, it is possible to do an O_DIRECT write and have it not be persistent if it reaches block device hardware but was never actually written to persistent storage there, and yes this can happen.  O_SYNC means that the driver both issues the write and blocks until the write is guaranteed to persist.  

Obviously O_SYNC can be a performance killer because the application has to wait for the device to respond with status showing that the write is now persistent.  So for random workloads it is possible to use asynchronous I/O to get many requests of this type to be submitted simultaneously - now the device can maintain an internal queue of active requests and the host can keep the device busy and also schedule I/O more efficiently using the Linux I/O scheduler (typically the **deadline** scheduler).

## Ceph RBD writes

With Ceph RBD block storage, writeback caching in the RBD client is NOT ENABLED unless it sees the application issue a sync (request flush of all writes to storage device) at least once.  Using the **fsync=1024** option in your fio job file can accomplish this  - this parameter will issue an fsync() call from fio every 1024 writes - the number 1024 is not sacred, adjust as necessary for your workload.   Note that writeback caching may be expensive for your guest in CPU - for small random writes, you may want to just disable writeback caching altogether and increase the number of in-flight writes with an increased **iodepth=N** parameter in your job file.    But for small sequential writes, writeback caching can be extremely efficient and can improve sequential write performance considerably by allowing the client to aggregate writes and issue parallel RADOS writes to underlying storage.  For more on this, see [Ceph RBD configuration](http://docs.ceph.com/docs/luminous/rbd/rbd-config-ref/) doc and [Ceph librbd programming](http://docs.ceph.com/docs/luminous/rbd/api/librbdpy/) doc.

# how to handle large host counts

If you are pushing limits of scalability with very large host counts, you have some additional tuning and workload parameters to consider.  It is very important that all fio processes and threads start to generate workload at the same time, and stop the workload at the same time.  Otherwise it is not valid to add the throughputs of these constituent threads to get the total system-wide workload, nor is it valid to obtain latency statistics!

## ARP cache increase

The default Linux parameters are sometimes too low for tests involving large numbers of VMs or containers, resulting in failure to cache IP addresses of all workload generates in the Linux ARP cache.  This can result in disconnected VMs.  To increase ARP cache size, see [this article](http://www.serveradminblog.com/2011/02/neighbour-table-overflow-sysctl-conf-tunning/) .  

## pdsh and ansible fanout

pdsh by default will only issue command in parallel to 32 hosts at a time.  Ansible will only issue command in parallel to 5 hosts by default.  This is good enough for many situations, but if you have a long running command that needs to run on more hosts in parallel than this, both pdsh and ansible have a **-f** parameter, but be careful with this because of the next problem.

## limit on simultaneous ssh sessions

ssh by default will not handle more than about 10 simultaneous ssh sessions started per second, but it can handle a very large number of concurrent sessions.  One tunable for sshd is the maximum number of sessions coming into a particular host, see [this article](http://unix.stackexchange.com/questions/22965/limits-of-ssh-multiplexing).

## fio startdelay parameter

It takes a while for fio to initiate workload on the entire set of hosts (much faster than ssh though).  We don't want the system getting busy while threads are being started!  Using the fio **startdelay=K** parameter (where K is number of seconds to wait before starting fio job) in your job file can allow the test driver to start fio workload generator processes without having them make the system busy right away, maximizing the chance of having all threads/processes start at approximately the same time.  

** fio ramp_time parameter

When cache has been dropped in a large cluster, the metadata kept in hosts' Linux buffer caches has been removed so it is not in its normal operating state anymore.  To let these metadata caches warm up a bit before unleashing the full workload, you can use the fio **ramp_time=K** parameter (where K is number of seconds to grow workload to full rate).  This is often used with random I/O tests, not sure of its applicability to sequential I/O tests.

FIXME: I'm guessing this has to be used with iops_rate=N parameter since otherwise fio would not know how to grow the IOPS rate.

# cache dropping 

In order to get reproducible, accurate results in a short amount of test time, you do not want to have client or server caching read data.  Why?  When doing performance tests, we want tests to cover a wide range of data points in a short time duration, but in real life, the cluster is run for months or even years without interruption, on amounts of data that are far greater than what we can access during the short performance test.  In order for our performance tests to match the steady-state throughput obtainable by the real users, we need to eliminate caching effects so that data is traversing the entire data path between block devices and application (Note: there are cases where it's ok to test the cache performance, as long as that is your intent!).  

To eliminate caching effects with pbench-fio, a new **--pre-iteration-script** option has been added.  This command is run by the test driver before each data point.  For example,  you could use the syntax **--pre-iteration-script=drop-cache.sh** , where this script looks like this:

    pdsh -S -w ^vms.list 'sync ; echo 3 > /proc/sys/vm/drop_caches'
    pdsh -S -w ^ceph-osd-nodes.list 'sync ; echo 3 > /proc/sys/vm/drop_caches'

This command should empty out the Linux buffer cache both on the guests and on the Ceph OSD hosts so that no data or metadata is cached there.  

The RBD cache is not cleared by this procedure, but the RBD cache is relatively small, 32 MB/guest, and so the significance of any caching there is not that great, particularly for workloads where you are using O_DIRECT and thereby bypassing the RBD cache.  To really flush the RBD cache, you would be forced to detach each inder volume and then re-attach it to its guest.  

For FUSE filesystems such as Gluster or Cephfs, the above procedure would not be sufficient in some cases and you might have to unmount and remount the filesystem, which is not a very time-consuming procedure.

Containers are more like processes than VMs, so that dropping Linux buffer cache on the node running the containers should be sufficient in most cases.

# warming up the system

If you drop cache, you need to allow the system to warm up its caches and reach steady-state behavior.  It is desirable for there to be no free memory either for most of test so that memory recycling behavior is tested.  So you may need considerable runtime at large scale.  You can specify maximum fio runtime using **runtime=k** line in job file where k is number of seconds.  Using pbench-fio you can observe the warmup behavior and see if your time duration needs adjustment.

For cases where the file can be completely read/written before the test duration has finished, if you don't want the test to stop, you must specify **time_based=1** to force fio to keep doing I/O to the file.  For example, on sequential files, if it reaches the end of file, it will seek to beginning of the file and start over.   On random I/O, it will keep generating random offsets even if the entire file has been accessed.

# limiting IOPS

A successful test should show both high throughput and acceptable latency.  For random I/O tests, it is possible to bring the system to its knees by putting way more random I/O requests in flight than there are block devices to service them (i.e. increasing queue depth).  This can artificially drive up response time.  You can reduce queue depth by reducing **iodepth=k** parameter in the job file or reducing number of concurrent fio processes.  But another method that may be useful is to reduce the rate at which each fio process issues random I/O requests to a lower value than it would otherwise have.  You can do this with the **rate_iops=k** parameter in the job file.  For example, this was used to run a large cluster at roughly 3/4 of its throughput capacity for latency measurements.

# measuring latency percentiles

Usually when a latency requirement is defined in a SLA (service-level agreement) for a cluster, the implication is that *at any point in time* during the operation of the cluster, the Nth latency percentile will not exceed X seconds.  However, fio does not output that information directly in its normal logs - instead it outputs latency percentiles measured over the duration of the entire test run.  For short test this may be sufficient, but for longer tests or tests designed to measure *changes* in latency, you need to capture the variation in latency percentiles over time.   The new fio histogram logging feature helps you do that.  It uses the histogram data structures internal to every fio process, emitting this histogram to a log file at a user-specified interval.  A post-processing tool, [fio-histo-log-pctiles.py](https://github.com/axboe/fio/blob/master/tools/hist/fio-histo-log-pctiles.py), then reads in these histogram logs and outputs latency percentiles over time.   pbench's postprocessing tool runs it and then graphs the results.  Documentation is [here](https://github.com/axboe/fio/blob/master/doc/fio-histo-log-pctiles.pdf).  The job file parameters **write_hist_log=h** and **hist_log_msec** control the pathnames and interval for histogram logging.

# examples

Here are some common use cases for distributed fio.

## example of OpenStack Cinder volumes

Advice: do everything on smallest possible scale to start with, until you get your input files to work, then scale it out.

construct a list of virtual machine IP addresses which are reachable from your test driver with ssh using no password.  These virtual machines should all have a cinder volume attached (i.e. /dev/vdb inside VM).  You should format the cinder volume from inside the VM with a Linux filesystem such as XFS

    testdriver# export PDSH_RCMD_TYPE=ssh
    testdriver# alias mypdsh="pdsh -S -w ^vms.list"

make sure it's not already mounted

    testdriver# mypdsh 'umount /mnt/fio'

For OpenStack, it's a good idea to preallocate RBD images so that you get consistent performance results.  To do this, you can dd to /dev/vdb like this (it could take a while):

    testdriver# mypdsh -f 128 'dd if=/dev/zero of=/dev/vdb bs=4096k conv=fsync'
    
Now format the filesystems for each cinder volume and mount them:

    testdriver# mypdsh -f 128 'mkfs -t xfs /dev/vdb && mkdir -p /mnt/fio && mount -t xfs -o noatime /dev/vdb /mnt/fio && mkdir /mnt/fio/files'
           
Then you construct a fio job file for your initial sequential tests, and this will also create the files for the subsequent tests.  certain parameters have to be specified with the string `$@` because pbench-fio wants to fill them in.   It might look something like this:

    [global]
    # size of each FIO file (in MB)
    size=$@
    # do not use gettimeofday, much too expensive for KVM guests
    clocksource=clock_gettime
    # give fio workers some time to get launched on remote hosts
    startdelay=5
    # files accessed by fio are in this directory
    directory=$@
    # write fio latency logs in /var/tmp with "fio" prefix
    write_lat_log=/var/tmp/fio
    # write a record to latency log once per second
    log_avg_msec=1000
    # write fio histogram logs in /var/tmp/ with "fio" prefix
    write_hist_log=/var/tmp/fio
    # write histogram record once every 10 seconds
    log_hist_msec=10
    # only one process per host
    numjobs=1
    # do an fsync on file before closing it (has no effect for reads)
    fsync_on_close=1
    # what's this?
    per_job_logs=1
    
    [sequential]
    rw=$@
    bs=$@
    # do not lay out the file before the write test, 
    # create it as part of the write test
    create_on_open=1
    # do not create just one file at a time
    create_serialize=0

And you write it to a file named fio-sequential.job, then run it with a command like this one, which launches fio on 1K guests with json output format.

    /usr/local/bin/fio --client-file=vms.list --pre-iteration-script=drop-cache.sh \
       --rw=write,read -b 4,128,1024 -d /mnt/fio/files --max-jobs=1024 \
       --output-format=json fio-sequential.job

This will write the files in parallel to the mount point.  The sequential read test that follows can use the same job file.  The **--max-jobs** parameter should match the count of the number of records in the vms.list file (FIXME: is --max-jobs still needed?).

Since we are using buffered I/O, we can usually get away with using a small transfer size, since the kernel will do prefetching, but there are exceptions, and you may need to vary the **bs** parameter.

For random writes, the job file is a little more complicated.  Again the `[global]` section is the same but the workload-specific part needs to be more complex to express some new parameters:

    [random]
    rw=$@
    bs=$@
    # specify use of libaio 
    # to allow a single thread to launch multiple parallel I/O requests
    ioengine=libaio
    # how many parallel I/O requests should be attempted
    iodepth=4
    # use O_DIRECT flag when opening a file
    direct=1
    # when the test is done and the file is closed, do an fsync first
    fsync_on_close=1
    # if we finish randomly accessing entire file, keep going until time is up
    time_based=1
    # test for 1/2 hour (gives caches time to warm up on large cluster)
    runtime=1800

The random read test can be performed using the same job file if you want.

    /usr/local/bin/fio --client-file=vms.list --pre-iteration-script=drop-cache.sh \
        --rw=randwrite,randread -b 4,128,1024 -d /mnt/fio/files --max-jobs=1024 \
        --output-format=json fio-random.job

## testing block devices with pbench-fio

In this example, each host has 2 Ceph RBD block devices, /dev/rbd0 and /dev/rbd1.  We want to generate a workload on
both of these block devices on all hosts - this is the only way to drive RBD to its performance limit.  This command
shows how to do that:

```
pbench-fio -c 192.168.121.64,192.168.121.112,192.168.121.158 \
  --job-file=/opt/pbench-agent/bench-scripts/templates/fio.job \
  --targets=/dev/rbd0,/dev/rbd1 \
  -b 4 -t read -s 64m
```

This will result in a total of 6 fio processes, 2 per host, each process accessing a different RBD block device.

## testing a distributed filesystem with pbench-fio

In this example, each host has a Cephfs mountpoint, /mnt/cephfs, but this could be an NFS, Gluster or any other
mountpoint to a distributed filesystem.

```
pbench-fio -c 192.168.121.64,192.168.121.112,192.168.121.158 \
  --job-file=/opt/pbench-agent/bench-scripts/templates/fio-shared-fs.job \
  --targets=/mnt/cephfs \
  -b 4 -t read -s 64m
```

In this case, the --targets parameter points to a shared directory (the mountpoint), and the special fio-shared-fs.job
file will assign this to the fio "directory" parameter.   When used with --client option, fio will 
then generate unique filenames (job number, host) pair and have these files assigned to fio processes
on each host.    At present, numjobs must be set to 1.


# syntax

For syntax details, use the command

    # pbench-fio --help

Note that not all fio parameters are specified by pbench-fio.  See [here](https://github.com/axboe/fio/blob/master/HOWTO)  for a page describing fio parameters in its github repo.  Parameters are part of pbench-fio command in order to allow pbench-fio to iterate over a broad range of tests in a single command.

This section stresses important parameters that are often used.  Where there is both a short-form (single-dash single-character) and a long-form (double-dash verbose) syntax for an option, we refer to it using the long-form syntax here.  

A CSV list is a comma-separated list of values with no embedded spaces.

Parameter data value other than these types are strings which are specified below.
* int - integer
* uint - non-negative integer 
* bool - boolean, in fio this is either 0 (false) or 1 (true)

Here are the pbench-fio parameters:

* **--test-types=type1,type2,...** - CSV list of fio-defined test types.  typical test types are:
  * write - sequentially write to file/device
  * read - sequentially read from file/device
  * randwrite - randomly write to file/device
  * randread - randomly read from file/device
  * randrw - use mixed random read/write mix with percentage specified in fio job file
* **--direct=boolean** - 1 means use **O_DIRECT** flag at open time to bypass buffer cache, default is 0.
* **--sync=boolean** - 1 means use **O_SYNC** flag at open time, default is 0 (data not guaranteed to be persistent).
* **--runtime=uint** - run the workload for k seconds (default is to run the workload until the entire file/device has been read/written.
* **--ramptime=uint** - time in seconds to warm up test before taking measurements (default is 0)
* **--block-sizes=int,int,...** - CSV list containing block sizes to use.  A "block size" is the I/O request size in KB.
* **--file-size=s1,s2,...** - specify file sizes to use when tests run on a filesystem.  For files, default is the entire pre-existing file.  For devices, default value is the entire device.
* **--targets=d1,d2,...** - specify CSV list of directories or block devices.
* **--directory=path** - single directory where fio operations will be performed (on all hosts)
* **--ioengine=libaio** - an ioengine is an fio module that uses a specific system call interface or library to generate I/O requests.  The default is sync, which uses conventional (read,write,pread,pwrite) interface, and for POSIX filesystems, an alternative to this for random I/O is the **libaio** interface, which supports asynchronous I/O requests (multiple I/O requests active from a single thread).
* **--iodepth=uint** - this parameter is only relevant with the **libaio** or other ioengines that support asynchronous I/O requests (not the default sync ioengine).  It specifies how many I/O requests at a time should be active from a single fio thread/process.
* **--client-file=path** - this is a pbench-fio-specific parameter that specifies a set of workload generators in a text file, 1 hostname/IP per record.  Default is "localhost".
* **--clients=h1,h2...** - this parameter specifies a set of workload generators as a CSV list of hostname/IP values.  Default is "localhost".
* **--numjobs=uint** - the total number of "jobs" to run.  This is typically set to the number of clients above.  Typically in the job file, you use numjobs=1.
* **--pre-iteration-script=path** - this points to a local executable script (doesn't have to be bash) that will execute before each sample is run.  For an example of how this can be useful, see cache-dropping section above.
* **--max-stddev=uint** - maximum percent deviation (100.0 \* standard deviation / mean) allowed for a successful test.  If you get test failures, consider either lengthening your test, changing test procedure to improve repeatability, or increasing this parameter.  Default is 5%.
