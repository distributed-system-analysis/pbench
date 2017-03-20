#!/usr/bin/env python3

# From DSA/satools/satools/
# https://github.com/distributed-system-analysis/satools

"""
A simple module to facilitate reading sa binary data files, providing classes
appropriate to different versions of the various binary data file formats, and
simple methods for dumping the data.

Test in this tree via:

    for i in samples/sa.* ; do echo $i; python sysstat.py $i ; done

/*
 ***************************************************************************
 * Definitions of header structures.
 *
 * Format of system activity data files (from at least FORMAT_MAGIC 0x2170 and later):
 *   __
 *  |
 *  | file_magic structure
 *  |
 *  |--
 *  |
 *  | file_header structure
 *  |
 *  |--                         --|
 *  |                             |
 *  | file_activity structure     | * sa_nr_act
 *  |                             |
 *  |--                         --|
 *  |                             |
 *  | record_header structure     |
 *  |                             |
 *  |--                           | * <count>
 *  |                             |
 *  | Statistics structures...(*) |
 *  |                             |
 *  |--                         --|
 *
 * (*)Note: If it's a special record, we may find a comment instead of
 * statistics (R_COMMENT record type) or the number of CPU items (R_RESTART
 * record type).
 ***************************************************************************
 */
"""

import sys, time, os.path, os, lzma
from datetime import datetime
from ctypes import Structure, c_int, c_uint, c_ushort, c_uint8, c_ulong, c_char, c_ulonglong
from abc import ABCMeta, abstractmethod
from contextlib import closing


class Corruption(Exception):
    """
    sa binary data file is corrupted somehow.
    """
    pass


class Invalid(Exception):
    """
    sa binary data file is corrupted somehow.
    """
    pass


class Truncated(Exception):
    """
    sa binary data file is corrupted somehow.
    """
    pass


DEBUG = False

TWO_DAYS_SECONDS = (2 * 24 * 60 * 60)

#/* Maximum length of a comment */
MAX_COMMENT_LEN = 64

#define UTSNAME_LEN     65
UTSNAME_LEN = 65

#/* Get IFNAMSIZ */
#include <net/if.h>
#ifndef IFNAMSIZ
#define IFNAMSIZ 16
#endif
#define MAX_IFACE_LEN   IFNAMSIZ
MAX_IFACE_LEN = 16

#/*
# * Sysstat magic number. Should never be modified.
# * Indicate that the file was created by sysstat.
# */
##define SYSSTAT_MAGIC  0xd596
SYSSTAT_MAGIC = 0xd596

#/* Record type */
#/*
# * R_STATS means that this is a record of statistics.
# */
#define R_STATS 1
R_STATS = 1
#/*
# * R_RESTART means that this is a special record containing
# * a LINUX RESTART message.
# */
#define R_RESTART 2
R_RESTART = 2
R_DUMMY = 2    # Under 2169 formats
#/*
# * R_LAST_STATS warns sar that this is the last record to be written
# * to file before a file rotation, and that the next data to come will
# * be a header file.
# * Such a record is tagged R_STATS anyway before being written to file.
# */
#define R_LAST_STATS 3
R_LAST_STATS = 3
#/*
# * R_COMMENT means that this is a special record containing
# * a comment.
# */
#define R_COMMENT 4
R_COMMENT = 4

# 0x2169 based formats, add "_B" to differentiate.
#/* Define activities */
A_PROC_B      = 0x000001
A_CTXSW_B     = 0x000002
A_CPU_B       = 0x000004
A_IRQ_B       = 0x000008
A_ONE_IRQ_B   = 0x000010
A_SWAP_B      = 0x000020
A_IO_B        = 0x000040
A_MEMORY_B    = 0x000080
A_SERIAL_B    = 0x000100
A_NET_DEV_B   = 0x000200
A_NET_EDEV_B  = 0x000400
A_DISK_B      = 0x000800
A_PID_B       = 0x001000
A_CPID_B      = 0x002000
A_NET_NFS_B   = 0x004000
A_NET_NFSD_B  = 0x008000
A_PAGE_B      = 0x010000
A_MEM_AMT_B   = 0x020000
A_KTABLES_B   = 0x040000
A_NET_SOCK_B  = 0x080000
A_QUEUE_B     = 0x100000
#define A_LAST      0x100000

#/* Activities */
A_CPU = 1
A_PCSW = 2
A_IRQ = 3
A_SWAP = 4
A_PAGE = 5
A_IO = 6
A_MEMORY = 7
A_KTABLES = 8
A_QUEUE = 9
A_SERIAL = 10
A_DISK = 11
A_NET_DEV = 12
A_NET_EDEV = 13
A_NET_NFS = 14
A_NET_NFSD = 15
A_NET_SOCK = 16
A_NET_IP = 17
A_NET_EIP = 18
A_NET_ICMP = 19
A_NET_EICMP = 20
A_NET_TCP = 21
A_NET_ETCP = 22
A_NET_UDP = 23
A_NET_SOCK6 = 24
A_NET_IP6 = 25
A_NET_EIP6 = 26
A_NET_ICMP6 = 27
A_NET_EICMP6 = 28
A_NET_UDP6 = 29
A_PWR_CPUFREQ = 30


class FileMagic(Structure):
    """
As of the final git v10.2.1:

This structure should only be extended in the future, so can serve as the
generic base structure from which we can interrupt the initial bytes of a file
to determine what the actual format version is for the rest of the file. If it
changes in size, which is likely for 10.3.x and later, we can define another
version for that specific number and insert it in the table below.

/*
 * Datafile format magic number.
 * Modified to indicate that the format of the file is
 * no longer compatible with that of previous sysstat versions.
 */
#define FORMAT_MAGIC    0x2171

/* Structure for file magic header data */
struct file_magic {
    /*
     * This field identifies the file as a file created by sysstat.
     */
    unsigned short sysstat_magic;
    /*
     * The value of this field varies whenever datafile format changes.
     */
    unsigned short format_magic;
    /*
     * Sysstat version used to create the file.
     */
    unsigned char  sysstat_version;
    unsigned char  sysstat_patchlevel;
    unsigned char  sysstat_sublevel;
    unsigned char  sysstat_extraversion;
};

#define FILE_MAGIC_SIZE (sizeof(struct file_magic))
    """
    _fields_ = [ ('sysstat_magic', c_ushort),
                 ('format_magic', c_ushort),
                 ('sysstat_version', c_uint8),
                 ('sysstat_patchlevel', c_uint8),
                 ('sysstat_sublevel', c_uint8),
                 ('sysstat_extraversion', c_uint8)
                 ]
    #FORMAT_MAGIC = 0x2171
    SIZE = ((2 * 2)
            + (4 * 1))

    def dump(self, *args, **kwargs):
        print("file_magic:")
        print("\tsysstat_magic = 0x%04x" % self.sysstat_magic)
        print("\tformat_magic = 0x%04x" % self.format_magic)
        print("\tsysstat_version", repr(self.sysstat_version))
        print("\tsysstat_patchlevel", repr(self.sysstat_patchlevel))
        print("\tsysstat_sublevel", repr(self.sysstat_sublevel))
        print("\tsysstat_extraversion", repr(self.sysstat_extraversion))


class FileHeader(Structure):
    """
    File Header structure shared by format versions under a 0xd596
    SYSSTAT_MAGIC value:

        0x2170 (9.0.0, RHEL 6.x),
        0x1170 (RHEL 6.5+),
        0x2171 (10.1.5, RHEL 7-Beta1, Fedora 19+)

/* Header structure for system activity data file */
struct file_header {
    /*
     * Timestamp in seconds since the epoch.
     */
    unsigned long sa_ust_time   __attribute__ ((aligned (8)));
    /*
     * Number of activities saved in the file
     */
    unsigned int sa_nr_act      __attribute__ ((aligned (8)));
    /*
     * Current day, month and year.
     * No need to save DST (Daylight Saving Time) flag, since it is not taken
     * into account by the strftime() function used to print the timestamp.
     */
    unsigned char sa_day;
    unsigned char sa_month;
    unsigned char sa_year;
    /*
     * Size of a long integer. Useful to know the architecture on which
     * the datafile was created.
     */
    char sa_sizeof_long;
    /*
     * Operating system name.
     */
    char sa_sysname[UTSNAME_LEN];
    /*
     * Machine hostname.
     */
    char sa_nodename[UTSNAME_LEN];
    /*
     * Operating system release number.
     */
    char sa_release[UTSNAME_LEN];
    /*
     * Machine architecture.
     */
    char sa_machine[UTSNAME_LEN];
};

#define FILE_HEADER_SIZE    (sizeof(struct file_header))
    """
    _fields_ = [ ('sa_ust_time', c_ulong),
                 ('sa_nr_act', c_uint),
                 ('sa_day', c_uint8),
                 ('sa_month', c_uint8),
                 ('sa_year', c_uint8),
                 ('sa_sizeof_long', c_char),
                 ('sa_sysname', c_char * UTSNAME_LEN),
                 ('sa_nodename', c_char * UTSNAME_LEN),
                 ('sa_release', c_char * UTSNAME_LEN),
                 ('sa_machine', c_char * UTSNAME_LEN),
                 ('_alignment_padding', c_uint),         # Padding due to alignment of first element?
                 ]
    SIZE = ((1 * 8)
            + (1 * 4)
            + (4 * 1)
            + (4 * UTSNAME_LEN)
            + 4)

    def dump(self, format_magic, *args, **kwargs):
        print("file_header (0x%04x):" % format_magic)
        print("\tsa_ust_time", repr(self.sa_ust_time), datetime.utcfromtimestamp(self.sa_ust_time))
        print("\tsa_nr_act", repr(self.sa_nr_act))
        print("\tsa_day", repr(self.sa_day))
        print("\tsa_month", repr(self.sa_month))
        print("\tsa_year", repr(self.sa_year))
        print("\tsa_sizeof_long", repr(self.sa_sizeof_long))
        print("\tsa_sysname", repr(self.sa_sysname))
        print("\tsa_nodename", repr(self.sa_nodename))
        print("\tsa_release", repr(self.sa_release))
        print("\tsa_machine", repr(self.sa_machine))


class FileStats2169(Structure):
    """
    File Header layout for sysstat 7.x.x versions (RHEL 5.x, bascially), that
    is, those with a file magic number of 0x2169.

struct file_stats {
   /* --- LONG LONG --- */
   /* Machine uptime (multiplied by the # of proc) */
   unsigned long long uptime         __attribute__ ((aligned (16)));
   /* Uptime reduced to one processor. Set *only* on SMP machines */
   unsigned long long uptime0        __attribute__ ((aligned (16)));
   unsigned long long context_swtch  __attribute__ ((aligned (16)));
   unsigned long long cpu_user       __attribute__ ((aligned (16)));
   unsigned long long cpu_nice       __attribute__ ((aligned (16)));
   unsigned long long cpu_system     __attribute__ ((aligned (16)));
   unsigned long long cpu_idle       __attribute__ ((aligned (16)));
   unsigned long long cpu_iowait     __attribute__ ((aligned (16)));
   unsigned long long cpu_steal      __attribute__ ((aligned (16)));
   unsigned long long irq_sum        __attribute__ ((aligned (16)));
   /* --- LONG --- */
   /* Time stamp (number of seconds since the epoch) */
   unsigned long ust_time            __attribute__ ((aligned (16)));
   unsigned long processes           __attribute__ ((aligned (8)));
   unsigned long pgpgin              __attribute__ ((aligned (8)));
   unsigned long pgpgout             __attribute__ ((aligned (8)));
   unsigned long pswpin              __attribute__ ((aligned (8)));
   unsigned long pswpout             __attribute__ ((aligned (8)));
   /* Memory stats in kB */
   unsigned long frmkb               __attribute__ ((aligned (8)));
   unsigned long bufkb               __attribute__ ((aligned (8)));
   unsigned long camkb               __attribute__ ((aligned (8)));
   unsigned long tlmkb               __attribute__ ((aligned (8)));
   unsigned long frskb               __attribute__ ((aligned (8)));
   unsigned long tlskb               __attribute__ ((aligned (8)));
   unsigned long caskb               __attribute__ ((aligned (8)));
   unsigned long nr_running          __attribute__ ((aligned (8)));
   unsigned long pgfault             __attribute__ ((aligned (8)));
   unsigned long pgmajfault          __attribute__ ((aligned (8)));
   /* --- INT --- */
   unsigned int  dk_drive            __attribute__ ((aligned (8)));
   unsigned int  dk_drive_rio        __attribute__ ((packed));
   unsigned int  dk_drive_wio        __attribute__ ((packed));
   unsigned int  dk_drive_rblk       __attribute__ ((packed));
   unsigned int  dk_drive_wblk       __attribute__ ((packed));
   unsigned int  file_used           __attribute__ ((packed));
   unsigned int  inode_used          __attribute__ ((packed));
   unsigned int  super_used          __attribute__ ((packed));
   unsigned int  super_max           __attribute__ ((packed));
   unsigned int  dquot_used          __attribute__ ((packed));
   unsigned int  dquot_max           __attribute__ ((packed));
   unsigned int  rtsig_queued        __attribute__ ((packed));
   unsigned int  rtsig_max           __attribute__ ((packed));
   unsigned int  sock_inuse          __attribute__ ((packed));
   unsigned int  tcp_inuse           __attribute__ ((packed));
   unsigned int  udp_inuse           __attribute__ ((packed));
   unsigned int  raw_inuse           __attribute__ ((packed));
   unsigned int  frag_inuse          __attribute__ ((packed));
   unsigned int  dentry_stat         __attribute__ ((packed));
   unsigned int  load_avg_1          __attribute__ ((packed));
   unsigned int  load_avg_5          __attribute__ ((packed));
   unsigned int  load_avg_15         __attribute__ ((packed));
   unsigned int  nr_threads          __attribute__ ((packed));
   unsigned int  nfs_rpccnt          __attribute__ ((packed));
   unsigned int  nfs_rpcretrans      __attribute__ ((packed));
   unsigned int  nfs_readcnt         __attribute__ ((packed));
   unsigned int  nfs_writecnt        __attribute__ ((packed));
   unsigned int  nfs_accesscnt       __attribute__ ((packed));
   unsigned int  nfs_getattcnt       __attribute__ ((packed));
   unsigned int  nfsd_rpccnt         __attribute__ ((packed));
   unsigned int  nfsd_rpcbad         __attribute__ ((packed));
   unsigned int  nfsd_netcnt         __attribute__ ((packed));
   unsigned int  nfsd_netudpcnt      __attribute__ ((packed));
   unsigned int  nfsd_nettcpcnt      __attribute__ ((packed));
   unsigned int  nfsd_rchits         __attribute__ ((packed));
   unsigned int  nfsd_rcmisses       __attribute__ ((packed));
   unsigned int  nfsd_readcnt        __attribute__ ((packed));
   unsigned int  nfsd_writecnt       __attribute__ ((packed));
   unsigned int  nfsd_accesscnt      __attribute__ ((packed));
   unsigned int  nfsd_getattcnt      __attribute__ ((packed));
   /* --- CHAR --- */
   /* Record type: R_STATS or R_DUMMY */
   unsigned char record_type         __attribute__ ((packed));
   /*
    * Time stamp: hour, minute and second.
    * Used to determine TRUE time (immutable, non locale dependent time).
    */
   unsigned char hour   /* (0-23) */ __attribute__ ((packed));
   unsigned char minute /* (0-59) */ __attribute__ ((packed));
   unsigned char second /* (0-59) */ __attribute__ ((packed));
};
    """
    _fields_ = [
        # --- LONG LONG ---
        ('uptime', c_ulonglong),             # 8 bytes, 16 byte aligned
        ('uptime_padding', c_ulong),         # ... 8 bytes of padding
        # Uptime reduced to one processor. Set *only* on SMP machines
        ('uptime0', c_ulonglong),
        ('uptime0_padding', c_ulong),        # ... 8 bytes of padding
        ('context_swtch', c_ulonglong),
        ('context_swtch_padding', c_ulong),  # ... 8 bytes of padding
        ('cpu_user', c_ulonglong),
        ('cpu_user_padding', c_ulong),       # ... 8 bytes of padding

        ('cpu_nice', c_ulonglong),
        ('cpu_nice_padding', c_ulong),       # ... 8 bytes of padding
        ('cpu_system', c_ulonglong),
        ('cpu_system_padding', c_ulong),     # ... 8 bytes of padding
        ('cpu_idle', c_ulonglong),
        ('cpu_idle_padding', c_ulong),       # ... 8 bytes of padding

        ('cpu_iowait', c_ulonglong),
        ('cpu_iowait_padding', c_ulong),     # ... 8 bytes of padding
        ('cpu_steal', c_ulonglong),
        ('cpu_steal_padding', c_ulong),      # ... 8 bytes of padding
        ('irq_sum', c_ulonglong),
        ('irq_sum_padding', c_ulong),        # ... 8 bytes of padding
        # --- LONG ---
        # Time stamp (number of seconds since the epoch)
        ('ust_time', c_ulong),               # 8 bytes, 8 byte aligned
        ('processes', c_ulong),
        ('pgpgin', c_ulong),

        ('pgpgout', c_ulong),
        ('pswpin', c_ulong),
        ('pswpout', c_ulong),
        # Memory stats in kB
        ('frmkb', c_ulong),
        ('bufkb', c_ulong),
        ('camkb', c_ulong),
        ('tlmkb', c_ulong),
        ('frskb', c_ulong),

        ('tlskb', c_ulong),
        ('caskb', c_ulong),
        ('nr_running', c_ulong),
        ('pgfault', c_ulong),
        ('pgmajfault', c_ulong),
        # --- INT ---
        ('dk_drive', c_uint),                # 4 bytes, packed
        ('dk_drive_rio', c_uint),
        ('dk_drive_wio', c_uint),
        ('dk_drive_rblk', c_uint),
        ('dk_drive_wblk', c_uint),

        ('file_used', c_uint),
        ('inode_used', c_uint),
        ('super_used', c_uint),
        ('super_max', c_uint),
        ('dquot_used', c_uint),

        ('dquot_max', c_uint),
        ('rtsig_queued', c_uint),
        ('rtsig_max', c_uint),
        ('sock_inuse', c_uint),
        ('tcp_inuse', c_uint),

        ('udp_inuse', c_uint),
        ('raw_inuse', c_uint),
        ('frag_inuse', c_uint),
        ('dentry_stat', c_uint),
        ('load_avg_1', c_uint),

        ('load_avg_5', c_uint),
        ('load_avg_15', c_uint),
        ('nr_threads', c_uint),
        ('nfs_rpccnt', c_uint),
        ('nfs_rpcretrans', c_uint),

        ('nfs_readcnt', c_uint),
        ('nfs_writecnt', c_uint),
        ('nfs_accesscnt', c_uint),
        ('nfs_getattcnt', c_uint),
        ('nfsd_rpccnt', c_uint),

        ('nfsd_rpcbad', c_uint),
        ('nfsd_netcnt', c_uint),
        ('nfsd_netudpcnt', c_uint),
        ('nfsd_nettcpcnt', c_uint),
        ('nfsd_rchits', c_uint),

        ('nfsd_rcmisses', c_uint),
        ('nfsd_readcnt', c_uint),
        ('nfsd_writecnt', c_uint),
        ('nfsd_accesscnt', c_uint),
        ('nfsd_getattcnt', c_uint),
        # --- CHAR (uint8) ---
        # Record type: R_STATS or R_DUMMY
        ('record_type', c_uint8),            # 1 byte, packed
        #
        # Time stamp: hour, minute and second.
        # Used to determine TRUE time (immutable, non locale dependent time).
        #
        ('hour', c_uint8),
        ('minute', c_uint8),
        ('second', c_uint8),
        #
        # 12 bytes of padding follow because of initial "__attribute__ ((aligned (16)))"
        #
        ('_alignment_padding0', c_uint),
        ('_alignment_padding1', c_uint),
        ]
    SIZE = ((10 * 16)   # 10 unsigned long longs
            + (16 * 8)  # 16 unsigned longs
            + (40 * 4)  # 40 unsigned ints
            + (4 * 1)   # 4 unsigned chars
            + 12)       # 12 bytes of padding

    def integrity(self, offset=-1, *args, **kwargs):
        for f in self._fields_:
            if not f[0].endswith('_padding'):
                continue
            val = getattr(self, f[0])
            if val == 0:
                continue
            if DEBUG:
                print(repr(f))
                self.dump(verbose=True)
                import pdb; pdb.set_trace()
            raise Corruption("non-zero filled padding: fs.%s = 0x%0x, offset: %d" % (f[0], val, offset))

    def dump(self, verbose=False, *args, **kwargs):
        print("file_stats: type %d, ts %r" % (self.record_type, time.gmtime(self.ust_time)))
        if not verbose:
            return
        for f in self._fields_:
            print("\t%s: %r" % (f[0], repr(getattr(self, f[0]))))


class StatsOneCpu2169(Structure):
    """
    CPU stats layout for a single CPU for sysstat 7.x.x versions (RHEL 5.x,
    bascially).

struct stats_one_cpu {
   unsigned long long per_cpu_idle    __attribute__ ((aligned (16)));
   unsigned long long per_cpu_iowait  __attribute__ ((aligned (16)));
   unsigned long long per_cpu_user    __attribute__ ((aligned (16)));
   unsigned long long per_cpu_nice    __attribute__ ((aligned (16)));
   unsigned long long per_cpu_system  __attribute__ ((aligned (16)));
   unsigned long long per_cpu_steal   __attribute__ ((aligned (16)));
   unsigned long long pad             __attribute__ ((aligned (16)));
};
    """
    _fields_ = [ ('per_cpu_idle', c_ulonglong),
                 ('per_cpu_idle_padding', c_ulong),
                 ('per_cpu_iowait', c_ulonglong),
                 ('per_cpu_iowait_padding', c_ulong),
                 ('per_cpu_user', c_ulonglong),
                 ('per_cpu_user_padding', c_ulong),
                 ('per_cpu_nice', c_ulonglong),
                 ('per_cpu_nice_padding', c_ulong),
                 ('per_cpu_system', c_ulonglong),
                 ('per_cpu_system_padding', c_ulong),
                 ('per_cpu_steal', c_ulonglong),
                 ('per_cpu_steal_padding', c_ulong),
                 ('pad', c_ulonglong),
                 ('pad_padding', c_ulong),
                 ]
    SIZE = (7 * 16)

    def dump(self):
        pass


class StatsSerial2169(Structure):
    """
    Serial stats layout for sysstat 7.x.x versions (RHEL 5.x, bascially).

struct stats_serial {
   unsigned int  rx       __attribute__ ((aligned (8)));
   unsigned int  tx       __attribute__ ((packed));
   unsigned int  frame    __attribute__ ((packed));
   unsigned int  parity   __attribute__ ((packed));
   unsigned int  brk      __attribute__ ((packed));
   unsigned int  overrun  __attribute__ ((packed));
   unsigned int  line     __attribute__ ((packed));
   unsigned char pad[4]   __attribute__ ((packed));
};
    """
    _fields_ = [ ('rx', c_uint),
                 ('tx', c_uint),
                 ('frame', c_uint),
                 ('parity', c_uint),
                 ('brk', c_uint),
                 ('overrun', c_uint),
                 ('line', c_uint),
                 ('pad', c_uint8 * 4),
                 ]
    SIZE = (7 * 4) + 4

    def dump(self):
        pass


NR_IRQS = 256

class StatInterrupt2169(Structure):
    """
    """
    _fields_ = [ ('interrupt', c_uint * NR_IRQS) ]

    SIZE = 4 * NR_IRQS

    def dump(self):
        pass


class StatsIrqCpu2169(Structure):
    """
    IRQ CPU stats layout for sysstat 7.x.x versions (RHEL 5.x, bascially).

struct stats_irq_cpu {
   unsigned int interrupt  __attribute__ ((aligned (8)));
   unsigned int irq        __attribute__ ((packed));
};
    """
    _fields_ = [ ('interrupt', c_uint),
                 ('irq', c_uint),
                 ]
    SIZE = (2 * 4)

    def dump(self):
        pass


class StatsNetDev2169(Structure):
    """
    Net Dev stats layout for sysstat 7.x.x versions (RHEL 5.x, bascially).

struct stats_net_dev {
   unsigned long rx_packets         __attribute__ ((aligned (8)));
   unsigned long tx_packets         __attribute__ ((aligned (8)));
   unsigned long rx_bytes           __attribute__ ((aligned (8)));
   unsigned long tx_bytes           __attribute__ ((aligned (8)));
   unsigned long rx_compressed      __attribute__ ((aligned (8)));
   unsigned long tx_compressed      __attribute__ ((aligned (8)));
   unsigned long multicast          __attribute__ ((aligned (8)));
   unsigned long collisions         __attribute__ ((aligned (8)));
   unsigned long rx_errors          __attribute__ ((aligned (8)));
   unsigned long tx_errors          __attribute__ ((aligned (8)));
   unsigned long rx_dropped         __attribute__ ((aligned (8)));
   unsigned long tx_dropped         __attribute__ ((aligned (8)));
   unsigned long rx_fifo_errors     __attribute__ ((aligned (8)));
   unsigned long tx_fifo_errors     __attribute__ ((aligned (8)));
   unsigned long rx_frame_errors    __attribute__ ((aligned (8)));
   unsigned long tx_carrier_errors  __attribute__ ((aligned (8)));
   char interface[MAX_IFACE_LEN]    __attribute__ ((aligned (8)));
};
    """
    _fields_ = [ ('rx_packets', c_ulong),
                 ('tx_packets', c_ulong),
                 ('rx_bytes', c_ulong),
                 ('tx_bytes', c_ulong),
                 ('rx_compressed', c_ulong),
                 ('tx_compressed', c_ulong),
                 ('multicast', c_ulong),
                 ('collisions', c_ulong),
                 ('rx_errors', c_ulong),
                 ('tx_errors', c_ulong),
                 ('rx_dropped', c_ulong),
                 ('tx_dropped', c_ulong),
                 ('rx_fifo_errors', c_ulong),
                 ('tx_fifo_errors', c_ulong),
                 ('rx_frame_errors', c_ulong),
                 ('tx_carrier_errors', c_ulong),
                 ('interface', c_char * MAX_IFACE_LEN),
                 ]
    SIZE = ((16 * 8)
            + MAX_IFACE_LEN)

    def dump(self):
        pass


class DiskStats2169(Structure):
    """
    Disk stats layout for sysstat 7.x.x versions (RHEL 5.x, bascially).

struct disk_stats {
   unsigned long long rd_sect  __attribute__ ((aligned (16)));
   unsigned long long wr_sect  __attribute__ ((aligned (16)));
   unsigned long rd_ticks      __attribute__ ((aligned (16)));
   unsigned long wr_ticks      __attribute__ ((aligned (8)));
   unsigned long tot_ticks     __attribute__ ((aligned (8)));
   unsigned long rq_ticks      __attribute__ ((aligned (8)));
   unsigned long nr_ios        __attribute__ ((aligned (8)));
   unsigned int  major         __attribute__ ((aligned (8)));
   unsigned int  minor         __attribute__ ((packed));
};
    """
    _fields_ = [ ('rd_sect', c_ulonglong),
                 ('rd_sect_padding', c_ulong),
                 ('wr_sect', c_ulonglong),
                 ('wr_sect_padding', c_ulong),
                 ('rd_ticks', c_ulong),
                 ('wr_ticks', c_ulong),
                 ('tot_ticks', c_ulong),
                 ('rq_ticks', c_ulong),
                 ('nr_ios', c_ulong),
                 ('major', c_uint),
                 ('minor', c_uint),
                 ]
    SIZE = ((2 * 16)
            + (5 * 8)
            + (2 * 4))

    def dump(self):
        pass


class FileHeader2169(Structure):
    """
    File Header layout for sysstat 7.x.x versions (RHEL 5.x, bascially).

/* System activity data file header */
struct file_hdr {
   /* --- LONG --- */
   /* Time stamp in seconds since the epoch */
   unsigned long sa_ust_time      __attribute__ ((aligned (8)));
   /* --- INT --- */
   /* Activity flag */
   unsigned int sa_actflag        __attribute__ ((aligned (8)));
   /* Number of processes to monitor ( {-x | -X } ALL) */
   unsigned int sa_nr_pid         __attribute__ ((packed));
   /* Number of interrupts per processor: 2 means two interrupts */
   unsigned int sa_irqcpu         __attribute__ ((packed));
   /* Number of disks */
   unsigned int sa_nr_disk        __attribute__ ((packed));
   /* Number of processors:
    * 0 means 1 proc and non SMP machine
    * 1 means 1 proc and SMP machine
    * 2 means two proc, etc.
    */
   unsigned int sa_proc           __attribute__ ((packed));
   /* Number of serial lines: 2 means two lines (ttyS00 and ttyS01) */
   unsigned int sa_serial         __attribute__ ((packed));
   /* Number of network devices (interfaces): 2 means two lines */
   unsigned int sa_iface          __attribute__ ((packed));
   /* --- SHORT --- */
   /* System activity data file magic number */
   unsigned short sa_magic        __attribute__ ((packed));
   /* file_stats structure size */
   unsigned short sa_st_size      __attribute__ ((packed));
   /* --- CHAR --- */
   /*
    * Current day, month and year.
    * No need to save DST (daylight saving time) flag, since it is not taken
    * into account by the strftime() function used to print the timestamp.
    */
   unsigned char sa_day           __attribute__ ((packed));
   unsigned char sa_month         __attribute__ ((packed));
   unsigned char sa_year          __attribute__ ((packed));
   /*
    * Size of a long integer. Useful to know the architecture on which
    * the datafile was created.
    */
   char sa_sizeof_long            __attribute__ ((packed));
   /* Operating system name */
   char sa_sysname[UTSNAME_LEN]   __attribute__ ((packed));
   /* Machine hostname */
   char sa_nodename[UTSNAME_LEN]  __attribute__ ((packed));
   /* Operating system release number */
   char sa_release[UTSNAME_LEN]   __attribute__ ((packed));
};

#define FILE_HDR_SIZE   (sizeof(struct file_hdr))
    """
    _fields_ = [ ('sa_ust_time', c_ulong),
                 ('sa_actflag', c_uint),
                 ('sa_nr_pid', c_uint),
                 ('sa_irqcpu', c_uint),
                 ('sa_nr_disk', c_uint),
                 ('sa_proc', c_uint),
                 ('sa_serial', c_uint),
                 ('sa_iface', c_uint),
                 ('sa_magic', c_ushort),
                 ('sa_st_size', c_ushort),
                 ('sa_day', c_uint8),
                 ('sa_month', c_uint8),
                 ('sa_year', c_uint8),
                 ('sa_sizeof_long', c_char),
                 ('sa_sysname', c_char * UTSNAME_LEN),
                 ('sa_nodename', c_char * UTSNAME_LEN),
                 ('sa_release', c_char * UTSNAME_LEN),
                 ('padding', c_char),
                 ]
    SIZE = (8
            + (7 * 4)
            + (2 * 2)
            + (4 * 1)
            + (3 * UTSNAME_LEN)
            + 1)

    def dump(self, *args, **kwargs):
        print("file_header (0x%04x):" % (self.sa_magic,))
        print("\tsa_ust_time", repr(self.sa_ust_time), datetime.utcfromtimestamp(self.sa_ust_time))
        print("\tsa_actflag", repr(self.sa_actflag))
        print("\tsa_nr_pid", repr(self.sa_nr_pid))
        print("\tsa_irqcpu", repr(self.sa_irqcpu))
        print("\tsa_nr_disk", repr(self.sa_nr_disk))
        print("\tsa_proc", repr(self.sa_proc))
        print("\tsa_serial", repr(self.sa_serial))
        print("\tsa_iface", repr(self.sa_iface))
        print("\tsa_magic 0x%04x" % self.sa_magic)
        print("\tsa_st_size", repr(self.sa_st_size))
        print("\tsa_day", repr(self.sa_day))
        print("\tsa_month", repr(self.sa_month))
        print("\tsa_year", repr(self.sa_year))
        print("\tsa_sizeof_long", repr(self.sa_sizeof_long))
        print("\tsa_sysname", repr(self.sa_sysname))
        print("\tsa_nodename", repr(self.sa_nodename))
        print("\tsa_release", repr(self.sa_release))


class FileHeaderOldGeneric(Structure):
    """
    Old style sa datafiles has the magic value at offset 36 (both for 32 and
    64 bits).
    """
    _fields_ = [ ('padding', c_char * 36),
                 ('sa_magic', c_ushort),
                 ]
    SIZE = 36 + 2


def check_readinto(obj, ret):
    if ret != obj.SIZE:
        if DEBUG:
            import pdb; pdb.set_trace()
        raise Truncated("Read %d, expected to read %d" % (ret, obj.SIZE))


def check_timestamp(fh, rh, prev_rh):
    if rh.ust_time == 0:
        raise Corruption("Record timestamp is zero")
    if (rh.ust_time - fh.sa_ust_time) < -60:
        # We have seen cases where the file header is one second later than
        # the first record, which is odd, but okay. So we only consider this
        # to be invalid if the header is more than a minute later than a
        # record.
        raise Invalid("Binary data file record, %s, earlier than header, %s" % (
            time.strftime("%c", time.gmtime(rh.ust_time)), time.strftime("%c", time.gmtime(fh.sa_ust_time))))
    if prev_rh:
        if rh.ust_time < prev_rh.ust_time:
            raise Invalid("Binary data file record, %s, earlier than previous, %s" % (
                time.strftime("%c", time.gmtime(rh.ust_time)), time.strftime("%c", time.gmtime(prev_rh.ust_time))))
        if (rh.ust_time - prev_rh.ust_time) > TWO_DAYS_SECONDS:
            raise Invalid("Binary data file record, %s, greater than two days from previous, %s" % (
                time.strftime("%c", time.gmtime(rh.ust_time)), time.strftime("%c", time.gmtime(prev_rh.ust_time))))
    else:
        if (rh.ust_time - fh.sa_ust_time) > TWO_DAYS_SECONDS:
            raise Invalid("Binary data file record, %s, greater than two days from header, %s" % (
                time.strftime("%c", time.gmtime(rh.ust_time)), time.strftime("%c", time.gmtime(fh.sa_ust_time))))


def read_extra_stats2169(fp, fh, wl=None):
    """
    These structures appear optionally, but always in this order.
    """
    total_read = 0
    if fh.sa_proc:
        c_read = 0
        for i in range(fh.sa_proc):
            cpu_stats = StatsOneCpu2169()
            ret = fp.readinto(cpu_stats)
            check_readinto(cpu_stats, ret)
            total_read += ret
            c_read += ret
            cpu_stats.dump()
            if wl is not None:
                wl.append(cpu_stats)
        if DEBUG:
            print("c_read = ", c_read)
    if (fh.sa_actflag & A_ONE_IRQ_B) == A_ONE_IRQ_B:
        interrupt_stats = StatInterrupt2169()
        ret = fp.readinto(interrupt_stats)
        check_readinto(interrupt_stats, ret)
        if DEBUG:
            print("int_read = ", ret)
        total_read += ret
        interrupt_stats.dump()
        if wl is not None:
            wl.append(interrupt_stats)
    if fh.sa_serial:
        s_read = 0
        for i in range(fh.sa_serial):
            serial_stats = StatsSerial2169()
            ret = fp.readinto(serial_stats)
            check_readinto(serial_stats, ret)
            s_read += ret
            total_read += ret
            serial_stats.dump()
            if wl is not None:
                wl.append(serial_stats)
        if DEBUG:
            print("s_read = ", s_read)
    if fh.sa_irqcpu:
        i_read = 0
        for i in range(fh.sa_proc * fh.sa_irqcpu):
            irq_cpu_stats = StatsIrqCpu2169()
            ret = fp.readinto(irq_cpu_stats)
            check_readinto(irq_cpu_stats, ret)
            i_read += ret
            total_read += ret
            irq_cpu_stats.dump()
            if wl is not None:
                wl.append(irq_cpu_stats)
        if DEBUG:
            print("i_read = ", i_read)
    if fh.sa_iface:
        if_read = 0
        for i in range(fh.sa_iface):
            net_dev_stats = StatsNetDev2169()
            ret = fp.readinto(net_dev_stats)
            check_readinto(net_dev_stats, ret)
            if_read += ret
            total_read += ret
            net_dev_stats.dump()
            if wl is not None:
                wl.append(net_dev_stats)
        if DEBUG:
            print("if_read = ", if_read)
    if fh.sa_nr_disk:
        d_read = 0
        for i in range(fh.sa_nr_disk):
            disk_stats = DiskStats2169()
            ret = fp.readinto(disk_stats)
            check_readinto(disk_stats, ret)
            d_read += ret
            total_read += ret
            disk_stats.dump()
            if wl is not None:
                wl.append(disk_stats)
        if DEBUG:
            print("d_read = ", d_read)
    return total_read


def process_file_2169(fp, fm, fh, fa, magic, callback=None):
    assert hasattr(fp, 'readinto')
    assert fm is None
    assert isinstance(fh, Structure)
    assert fa is None
    assert magic == 0x2169

    assert FileHeader2169.SIZE == 240,  "FileHeader2169.SIZE (%d) != 240"  % FileHeader2169.SIZE
    assert FileStats2169.SIZE == 464,   "FileStats2169.SIZE (%d) != 464"   % FileStats2169.SIZE
    assert StatsOneCpu2169.SIZE == 112, "StatsOneCpu2169.SIZE (%d) != 112" % StatsOneCpu2169.SIZE
    assert StatsSerial2169.SIZE == 32,  "StatsSerial2169.SIZE (%d) != 32"  % StatsSerial2169.SIZE
    assert StatsIrqCpu2169.SIZE == 8,   "StatsIrqCpu2169.SIZE (%d) != 8"   % StatsIrqCpu2169.SIZE
    assert StatsNetDev2169.SIZE == 144, "StatsNetDev2169.SIZE (%d) != 144" % StatsNetDev2169.SIZE
    assert DiskStats2169.SIZE == 80,    "DiskStats2169.SIZE (%d) != 80"    % DiskStats2169.SIZE

    if FileStats2169.SIZE != fh.sa_st_size:
        # If the file header is not valid, we're done
        if DEBUG:
            import pdb; pdb.set_trace()
        raise Invalid(
            "Invalid file header structure encountered,"
            " expected sizeof(struct file_stats) == %d"
            " for magic 0x2169, but found .sa_st_size = %d" % (
                FileStats2169.SIZE, fh.sa_st_size))

    if callback is not None:
        callback.start(file_header=fh)

    try:
        prev_fs = None
        fs = None
        while True:
            prev_fs = fs
            fs = FileStats2169()
            try:
                ret = fp.readinto(fs)
            except Exception:
                if DEBUG:
                    import pdb; pdb.set_trace()
                raise
            else:
                if ret == 0:
                    # Indicates EOF
                    break
                else:
                    check_readinto(fs, ret)
            fs.integrity(fp.tell() - fs.SIZE)
            check_timestamp(fh, fs, prev_fs)
            if fs.record_type == R_DUMMY:
                if callback is not None:
                    callback.handle_record(fs, record_payload=None)
                continue
            if callback is not None:
                write_list = []
            else:
                write_list = None
            ret = read_extra_stats2169(fp, fh, write_list)
            if callback is not None:
                callback.handle_record(fs, record_payload=write_list)
    finally:
        if callback is not None:
            callback.end()


class RecordHeader2170(Structure):
    """
/* Header structure for every record */
struct record_header {
    /*
     * Machine uptime (multiplied by the # of proc).
     */
    unsigned long long uptime   __attribute__ ((aligned (16)));
    /*
     * Uptime reduced to one processor. Always set, even on UP machines.
     */
    unsigned long long uptime0  __attribute__ ((aligned (16)));
    /*
     * Timestamp (number of seconds since the epoch).
     */
    unsigned long ust_time      __attribute__ ((aligned (16)));
    /*
     * Record type: R_STATS, R_RESTART,...
     */
    unsigned char record_type   __attribute__ ((aligned (8)));
    /*
     * Timestamp: Hour (0-23), minute (0-59) and second (0-59).
     * Used to determine TRUE time (immutable, non locale dependent time).
     */
    unsigned char hour;
    unsigned char minute;
    unsigned char second;
};

#define RECORD_HEADER_SIZE  (sizeof(struct record_header))
    """
    _fields_ = [ ('uptime', c_ulonglong),         # 8 bytes, __attribute__ ((aligned (16)))
                 ('uptime_padding', c_ulong),     # ... 8 bytes of padding for next alignment
                 ('uptime0', c_ulonglong),        # 8 bytes, __attribute__ ((aligned (16)))
                 ('uptime0_padding', c_ulong),    # ... 8 bytes of padding for next alignment
                 ('ust_time', c_ulong),           # 8 bytes, __attribute__ ((aligned (16)))
                 ('record_type', c_uint8),        # 1 byte, __attribute__ ((aligned (8)));
                 ('hour', c_uint8),               # 1 byte
                 ('minute', c_uint8),             # 1 byte
                 ('second', c_uint8),             # 1 byte
                 ('_alignment_padding', c_uint),  # 4 bytes of padding due to alignment?
                 ]
    SIZE = ((2 * 16)
            + (1 * 8)
            + (4 * 1)
            + (1 * 4))

    def integrity(self, offset=-1, *args, **kwargs):
        for f in self._fields_:
            if not f[0].endswith('_padding'):
                continue
            val = getattr(self, f[0])
            if val == 0:
                continue
            if DEBUG:
                print(repr(f))
                self.dump(verbose=True)
                import pdb; pdb.set_trace()
            raise Corruption("non-zero filled padding: rh.%s = 0x%0x, offset: %d" % (f[0], val, offset))

    def dump(self, verbose=False, *args, **kwargs):
        print("record_header: type %d, ts %r" % (self.record_type, time.gmtime(self.ust_time)))
        if not verbose:
            return
        for f in self._fields_:
            print("\t%s: %r" % (f[0], repr(getattr(self, f[0]))))


class FileActivitySummary(object):
    def __init__(self, fa, total_len):
        self.fa = fa
        self.total_len = total_len

    def dump(self, *args, **kwargs):
        print("file activity summary, total length: %d" % (self.total_len,))



class FileActivity2170(Structure):
    """
/* List of activities saved in file */
struct file_activity {
    /*
     * Identification value of activity.
     */
    unsigned int id  __attribute__ ((aligned (4)));
    /*
     * Number of items for this activity.
     */
    __nr_t nr        __attribute__ ((packed));
    /*
     * Size of an item structure.
     */
    int size         __attribute__ ((packed));
};
    """
    _fields_ = [ ('id', c_uint),
                 ('nr', c_int),
                 ('size', c_int),
                 ]
    SIZE = 3 * 4


def get_file_activity_2170(fp, fh):
    # Read file activities
    a_cpu = False
    file_activities = []
    total_len = 0
    for i in range(fh.sa_nr_act):
        act = FileActivity2170()
        ret = fp.readinto(act)
        check_readinto(act, ret)
        if act.nr <= 0:
            if DEBUG:
                import pdb; pdb.set_trace()
                print(repr(act))
            raise Invalid("activity count %d <= 0" % act.nr)
        file_activities.append(act)
        if act.id == A_CPU:
            a_cpu = True
        total_len += (act.nr * act.size)

    if not a_cpu:
        if DEBUG:
            import pdb; pdb.set_trace()
        raise Invalid("expected CPU activity")

    return FileActivitySummary(file_activities, total_len)


def get_file_activity_1170(fp, fh):
    return get_file_activity_2170(fp, fh)


def process_file_2170(fp, fm, fh, fa, magic, callback=None):
    assert hasattr(fp, 'readinto')
    assert isinstance(fm, Structure)
    assert isinstance(fh, Structure)
    assert isinstance(fa, FileActivitySummary)
    assert magic == 0x1170 or magic > 0x2169

    if callback is not None:
        callback.start(file_magic=fm, file_header=fh, file_activities=fa)

    try:
        prev_rh = None
        rh = None
        while True:
            prev_rh = rh
            rh = RecordHeader2170()
            try:
                ret = fp.readinto(rh)
            except Exception:
                if DEBUG:
                    import pdb; pdb.set_trace()
                raise
            else:
                if ret == 0:
                    # Indicates EOF
                    break
                else:
                    check_readinto(rh, ret)
            rh.integrity(fp.tell() - rh.SIZE)
            try:
                check_timestamp(fh, rh, prev_rh)
            except Invalid:
                if callback is not None:
                    do_raise = callback.handle_invalid(rh, prev_rh)
                else:
                    do_raise = True
                if do_raise:
                    raise

            if rh.record_type == R_COMMENT:
                fc = bytearray(MAX_COMMENT_LEN)
                ret = fp.readinto(fc)
                if ret != MAX_COMMENT_LEN:
                    if DEBUG:
                        import pdb; pdb.set_trace()
                    raise Truncated("Could not read entire comment,"
                                    " read %d, expected %d" % (ret, MAX_COMMENT_LEN))
                if callback is not None:
                    callback.handle_record(rh, record_payload=fc)
                continue
            elif rh.record_type == R_RESTART:
                if callback is not None:
                    callback.handle_record(rh, record_payload=None)
                continue
            act_buf = bytearray(fa.total_len)
            ret = fp.readinto(act_buf)
            if ret != fa.total_len:
                if DEBUG:
                    import pdb; pdb.set_trace()
                raise Truncated("Could not read all activities,"
                                " read %d, expected records of size %d" % (ret, fa.total_len))
            if callback is not None:
                callback.handle_record(rh, record_payload=act_buf)
    finally:
        if callback is not None:
            callback.end()


def process_file_1170(fp, fm, fh, fa, magic, callback=None):
    """
    For some reason, RHEL 6.5 patch sysstat to mark a changed file format
    using 0x1170. It is not clear where the format change came from, or what
    the difference is, but it did not affect sizing or layouts, as far as we
    can tell.
    """
    process_file_2170(fp, fm, fh, fa, magic, callback=callback)


ACTIVITY_MAGIC_BASE = 0x8a
ACTIVITY_MAGIC_UNKNOWN = 0x89

class FileActivity2171(Structure):
    """
/*
 * Base magical number for activities.
 */
#define ACTIVITY_MAGIC_BASE	0x8a
/*
 * Magical value used for activities with
 * unknown format (used for sadf -H only).
 */
#define ACTIVITY_MAGIC_UNKNOWN	0x89

/* List of activities saved in file */
struct file_activity {
	/*
	 * Identification value of activity.
	 */
	unsigned int id		__attribute__ ((aligned (4)));
	/*
	 * Activity magical number.
	 */
	unsigned int magic	__attribute__ ((packed));
	/*
	 * Number of items for this activity.
	 */
	__nr_t nr		__attribute__ ((packed));
	/*
	 * Number of sub-items for this activity.
	 */
	__nr_t nr2		__attribute__ ((packed));
	/*
	 * Size of an item structure.
	 */
	int size		__attribute__ ((packed));
};

#define FILE_ACTIVITY_SIZE	(sizeof(struct file_activity))
    """
    _fields_ = [ ('id', c_uint),
                 ('magic', c_int),
                 ('nr', c_int),
                 ('nr2', c_int),
                 ('size', c_int),
                 ]
    SIZE = 5 * 4


def get_file_activity_2171(fp, fh):
    # Read file activities
    a_cpu = False
    file_activities = []
    total_len = 0
    for i in range(fh.sa_nr_act):
        act = FileActivity2171()
        ret = fp.readinto(act)
        check_readinto(act, ret)
        if act.nr <= 0 or act.nr2 <= 0:
            if DEBUG:
                import pdb; pdb.set_trace()
                print(repr(act))
            raise Invalid("activity counts: (nr %d or nr2 %d) <= 0" % (act.nr, act.nr2))
        file_activities.append(act)
        if act.id == A_CPU:
            a_cpu = True
        total_len += (act.nr * act.nr2 * act.size)

    if not a_cpu:
        if DEBUG:
            import pdb; pdb.set_trace()
        raise Invalid("expected CPU activity")

    return FileActivitySummary(file_activities, total_len)


def process_file_2171(fp, fm, fh, fa, magic, callback=None):
    """
    While the format magic has changed, the actual on-disk format is not so
    different since the activities have already been processed. Since all the
    record reads are performed using the values stored in the activity set,
    the processing remains the same.
    """
    process_file_2170(fp, fm, fh, fa, magic, callback=callback)


class_map = {
    0x2169: {
        "file_magic": None,
        "file_header": FileHeader2169,
        "process_file": process_file_2169,
        "file_activity": None,
        "os-code": "5x",
        "rpm-versions": ("sysstat-7.0.0-3.el5",
                         "sysstat-7.0.2-1.el5",
                         "sysstat-7.0.2-3.el5",
                         "sysstat-7.0.2-3.el5_5.1",
                         "sysstat-7.0.2-11.el5",
                         "sysstat-7.0.2-12.el5",),
        },
    0x2170: {
        "file_magic": FileMagic,
        "file_header": FileHeader,
        "process_file": process_file_2170,
        "file_activity": get_file_activity_2170,
        "os-code": "64",
        "rpm-versions": ("sysstat-9.0.4-11.el6",
                         "sysstat-9.0.4-18.el6",
                         "sysstat-9.0.4-20.el6",),
        },
    0x1170: {
        "file_magic": FileMagic,
        "file_header": FileHeader,
        "process_file": process_file_1170,
        "file_activity": get_file_activity_1170,
        "os-code": "65",
        "rpm-versions": ("sysstat-9.0.4-22.el6",),
        },
    0x2171: {
        "file_magic": FileMagic,
        "file_header": FileHeader,
        "process_file": process_file_2171,
        "file_activity": get_file_activity_2171,
        "os-code": "f19",
        "rpm-versions": ("sysstat-10.1.5-1.el7",),
        },
    }


def fetch_fileheader_with_fp(fp):
    fm = FileMagic()
    ret = fp.readinto(fm)
    check_readinto(fm, ret)

    fp.seek(0)  # Reset to the beginning to read into the proper structure below.
    if fm.sysstat_magic == SYSSTAT_MAGIC:
        # We have a 9.0.0 and later version
        try:
            the_class_map = class_map[fm.format_magic]
        except KeyError:
            raise Invalid("Unrecognized new format magic: 0x%04d" % fm.format_magic)
        else:
            magic = fm.format_magic
    else:
        # Now we have an old style sa binary data file, where the file
        # header comes first, and the sa_magic field is at a defined
        # offset inside that header.
        fh = FileHeaderOldGeneric()
        ret = fp.readinto(fh)
        check_readinto(fh, ret)
        try:
            the_class_map = class_map[fh.sa_magic]
        except KeyError:
            raise Invalid("Unrecognized old sa magic: 0x%04d" % fh.sa_magic)
        else:
            magic = fh.sa_magic
        # Will need to re-read from the beginning of the file to get the right
        # mappings.
        fp.seek(0)

    try:
        fm = the_class_map['file_magic']()
    except TypeError:
        fm = None
    else:
        try:
            ret = fp.readinto(fm)
            check_readinto(fm, ret)
        except Exception as err:
            raise Invalid("Error reading file header: %s" % err)

    try:
        fh = the_class_map['file_header']()
        ret = fp.readinto(fh)
        check_readinto(fh, ret)
    except Exception as err:
        raise Invalid("Error reading file header: %s" % err)

    try:
        fa = the_class_map['file_activity'](fp, fh)
    except TypeError:
        fa = None
    except Exception as err:
        raise Invalid("Error reading file activities: %s" % err)

    return fm, fh, fa, magic


class ContentAction(object):
    """
    The callback object argument of the module method, verify_contents(),
    expects with these four methods.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def start(self, file_magic=None, file_header=None, file_activities=None):
        """
        Start the handling of a binary data file. The caller optionally
        provides the file_magic record, always provides the required
        file_header record, and optionally provides the file activities.
        """
        pass

    @abstractmethod
    def handle_record(self, record_header, record_payload=None):
        """
        Handle a record header, along with its optional payload.
        """
        pass

    @abstractmethod
    def handle_invalid(self, record_header, prev_record_header):
        """
        An invalid record header was encountered, the previous one is also
        provided for the callee to inspect.  If this method returns True, the
        processing will continue the exception, if False, the exception will
        be swallowed.
        """
        pass

    @abstractmethod
    def end(self):
        """
        By hook, or by crook, we have reached the end of the binary data
        file. No other methods will be invoked on the given object instance
        after this invocation.
        """
        pass


def verify_contents_fp(fp, tgt_hostname, callback):
    fm, fh, fa, magic = fetch_fileheader_with_fp(fp)
    try:
        the_class_map = class_map[magic]
    except KeyError:
        raise Invalid("Unrecognized old sa magic: 0x%04d" % magic)
    else:
        if tgt_hostname and (tgt_hostname != fh.sa_nodename.decode('utf-8')):
            raise Invalid("Target host name, %s, does not match file header node name, %s" % (tgt_hostname, fh.sa_nodename))
        process_file = the_class_map['process_file']
    process_file(fp, fm, fh, fa, magic, callback=callback)


def verify_contents(thefile, tgt_hostname=None, callback=None):
    """
    Given a sysstat binary data file verify that it contains a set of well
    formed data values.

    The optional 'tgt_hostname' argument is checked against the file header's
    stored hostname value.

    The optional 'callback' argument, if provided, should be an instance of
    the ContentAction class, where for each magic structure, file header, file
    activity set, record header and record payload read the appropriate method
    will be invoked, with the 'eof' method invoked at the end.

    One of the following exceptions will be raised if a problem is found with
    the file:

        Invalid: The file header or record header metadata values do not make
                 sense in relation to each other

        Corruption: The file appears to be corrupted in some way

        Truncated: The file does not appear to contain all the data as
                   described by the file header or a given record header
    """
    try:
        with lzma.open(thefile, "rb") as fp:
            verify_contents_fp(fp, tgt_hostname, callback)
    except lzma.LZMAError:
        with open(thefile, "rb") as fp:
            verify_contents_fp(fp, tgt_hostname, callback)


def fetch_os_code(magic):
    """
    Given a sysstat magic number value, return the "OS code" that maps to
    version of Fedora or RHEL.
    """
    try:
        the_class_map = class_map[magic]
    except KeyError:
        raise Invalid("Unrecognized old sa magic: 0x%04d" % magic)
    else:
        return the_class_map['os-code']


def fetch_fileheader(thefile):
    """
    Fetch the sysstat FileHeader object for the given file path.
    """
    try:
        with lzma.open(thefile, "rb") as fp:
            res = fetch_fileheader_with_fp(fp)
    except lzma.LZMAError:
        with open(thefile, "rb") as fp:
            res = fetch_fileheader_with_fp(fp)
    return res


if __name__ == "__main__":
    # When invoked as a progrem, we'll just check the first argument to see
    # that is has data in it, and if so, we'll process the header, fetch the
    # OS code, and verify its contents.

    if os.path.getsize(sys.argv[1]) == 0:
        print("Invalid - %s: empty data file" % (sys.argv[1],), file=sys.stderr)
        sys.exit(1)

    try:
        fm, fh, fa, magic = fetch_fileheader(sys.argv[1])
    except Invalid as e:
        print("Invalid - %s: %s" % (sys.argv[1], e), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print("Error - %s: %s" % (sys.argv[1], e), file=sys.stderr)
        sys.exit(1)
    else:
        if DEBUG or 1:
            fm.dump()
            fh.dump(fm.format_magic)
            fa.dump()
            val = fetch_os_code(magic)
            print("os_code = ", val)

    try:
        verify_contents(sys.argv[1])
    except Invalid as e:
        print("Invalid - %s: %s" % (sys.argv[1], e), file=sys.stderr)
        sys.exit(1)
    except Corruption as e:
        print("Corrupted - %s: %s" % (sys.argv[1], e), file=sys.stderr)
        sys.exit(1)
    except Truncated as e:
        sys.exit(1)
