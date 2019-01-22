#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-

# Author: Andrew Theurer
#
package SysStat;

use strict;
use warnings;
use Exporter qw(import);

our @EXPORT_OK = qw(get_pidstat_attributes);

sub get_pidstat_attributes {
	return qw(usr system guest CPU_PCT CPUID minflt_s majflt_s VSZ RSS MEM_PCT kB_rd_s kB_wr_s iodelay cswch_s nvcswch_s);
}

1;
