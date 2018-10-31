This page documents how pbench-uperf can help you with network performance testing.  Before covering the specific command-line syntax,
we discuss why you would use this tool and methods for utilizing it.

# network performance

Network performance has a huge impact on performance of distributed storage,
but is often not given the attention it deserves
during the planning and installation phases of the cluster lifecycle.

The purpose of pbench-uperf is to characterize the capacity
of your entire network infrastructure to support the desired level of traffic
induced by distributed storage, using multiple network connections in parallel.
After all, that's what your distributed storage will be doing with the network.

There are several network performance tools available such as netperf, iperf, and uperf, but
in their current form they do not directly measure network traffic flows between
sets of hosts, only 2 hosts at a time.

# examples motivating network testing

The two most common hardware problems impacting distributed storage are,
not surprisingly, disk drive failures and network failures.
Some of these failures do not cause hard errors and are more or less silent,
but instead cause performance degradation.
For example, with a bonded network interface containing two physical network interfaces,
if one of the physical interfaces fails (either port on NIC/switch, or cable),
then the bonded interface will stay up, but will have less performance
(how much less depends on the bonding mode).
Another error would be failure of an 10-GbE Ethernet interface to
autonegotiate speed to 10-Gbps --
sometimes network interfaces auto-negotiate to 1-Gbps instead.
If the TCP connection is experiencing a high rate of packet loss
or is not tuned correctly, it may not reach the full network speed supported by the hardware.

So why run parallel netperf sessions instead of just one?
There are a variety of network performance problems
relating to network topology (the way in which hosts are interconnected),
particularly network switch and router topology, that only manifest when
several pairs of hosts are attempting to transmit traffic
across the same shared resource,
which could be a trunk connecting top-of-rack switches or
a blade-based switch with insufficient bandwidth to switch backplane, for example.
Individual netperf/iperf sessions will not find these problems, but **pbench-uperf** will.

This test can be used to simulate flow of data through a distributed filesystem,
for example. If you want to simulate 4 Gluster clients, call them c1 through c4,
writing large files to a set of 2 servers, call them s1 and s2,
you can specify these (sender, receiver) pairs (we'll see how in a second):

     (c1,s1), (c2, s2), (c3, s1), (c4, s2)

If on the other hand you want to simulate reads, you can use these (sender, receiver) pairs:

    (s1, c1), (s2, c2), (s1, c3), (s2, c4)

Finally, if you want to simulate a mixed read-write workload, use these pairs:

    (c1,s1), (c2, s2), (c3, s1), (c4, s2), (s1, c1), (s2, c2), (s1, c3), (s2, c4)

More complicated flows can model behavior of non-native protocols,
where a cluster node acts as a proxy server -
it is a server (for non-native protocol) and a client (for native protocol).
For example, such protocols often induce full-duplex traffic
which can stress the network differently than unidirectional in/out traffic.
For example, try adding this set of flows to preceding flow:

    (s1, s2),.(s2, s3),.(s3, s4),.(s4, s1)

# how to run it

Use the command:

    # pbench-uperf -h

You typically run pbench-uperf from a head node or test driver that has password-less ssh access
to the set of machines being tested.
The hosts running the test do not need ssh access to each other --
they only have to allow password-less ssh access from the head node.

## firewalls

*you must ensure that the network firewall or poke holes in the firewall for pbench-uperf*.  Typically there are two possible firewall implementations encountered:

* the **firewalld** service
* the **iptables** service

to temporarily disable (this may give security folks heartburn):

    # systemctl stop firewalld
    # systemctl stop iptables

## syntax

Important test parameters are listed in their long form but there is also a short form available with **-h** :

* **--test-types** - stream, rr
  * **stream** is a unidirectional test which can establish whether network can achieve rated speed
  * **rr** stands for "request-response", and uses an exchange of messages between client and server.
* **--message-sizes** - list of message sizes in bytes
* **--runtime** - test measurement period in seconds
* **--protocols** - tcp or udp - UDP can be used to measure impact of packet loss on TCP throughput
* **--instances** - how many instances to run per host
* **--clients** - a comma-separated list of client hosts to use
* **--servers** - a comma-separated list of server hosts to use

**FIXME** - not all parameters documented yet.

For high network speeds, multiple uperf instances per node must be used to harness enough CPU power
to drive the network interface to full speed.

If your test duration is not high enough, you may start to see errors caused by a high standard deviation in test results.

The client and server lists should be the same length.
pbench-uperf will create a uperf session from clients[k] to servers[k],
where clients[k] is the k'th client in the --clients list, and
servers[k] is the k'th server in the --servers list.

# results

There are 2 basic forms of performance results:

* throughput -- how much work is done in a unit of time?
  * for **stream** test: Gbit/sec
    * response time is not measurable
  * for **rr** test: exchanges/sec
      response time -- average time between beginning of request send and end of response receive

The latter **rr** test is probably most important for understanding what to expect from distributed storage clients,
where read and write requests have to be acknowledged.
For example, if you have a 100-Gbit network with a round trip time of 1 millisec and a message size of 1 Mbit,
you can transmit the message in 10 microsec. but you can't get a response for 100 times that long!

Network utilization can be derived from pbench **sar**  Mbit/sec results on the network interfaces.

Scalability can be derived from running a series of these tests with varying numbers of network interfaces and hosts,
keeping the ratio of threads to interfaces constant.
