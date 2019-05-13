#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-

# Author: Andrew Theurer
#
package SysStat;

use strict;
use warnings;
use Data::Dumper;
use Exporter qw(import);

our @EXPORT_OK = qw(get_pidstat_attributes get_mpstat_cpumode_attributes get_sar_cpumode_attributes build_cpu_topology get_cpu_socket_core);

sub get_pidstat_attributes {
	# Headers for v12 of sysstat
	return qw(usr system guest wait CPU_PCT CPUID minflt_s majflt_s VSZ RSS MEM_PCT kB_rd_s kB_wr_s kB_ccwr_s iodelay cswch_s nvcswch_s);
}

sub get_mpstat_cpumode_attributes {
	# Headers for v12 of sysstat
	return qw(usr nice sys iowait irq soft steal guest gnice idle);
}

sub get_sar_cpumode_attributes {
	# Headers for v12 of sysstat
	return qw(usr nice sys iowait steal irq soft guest gnice idle);
}

sub build_cpu_topology {
	my $cpu_ref = shift; # Array reference to CPU information, index = cpuID, value = (socket, core)
	my $dir = shift;
	
	# There are a couple ways to get the topology depending on the information available at the time
	# of postprocessing. 
	#
	# First way is to look at the turbostat data, if available
	my $turbostat_file = $dir . "/../turbostat/turbostat-stdout.txt";
	if (defined $dir and -e $turbostat_file) {
		open (FH, $turbostat_file) || die "Could not open $turbostat_file";
		while (<FH>) {
			my $line = $_;
			chomp $line;
			#1556376077425: 0        0       0
			if ($line =~ /\d{13}:\s+(\d+)\s+(\d+)\s+(\d+).*/) {
				if (defined $$cpu_ref[$3]) {
					last; # We have found all of the cpuids
				} else {
					my @socket_core = ($1, $2);
					$$cpu_ref[$3] = \@socket_core;
				}
			}
		}
		close FH;
		return;
	}
	# Other methods will be added here, and may include:
	# - inspecting data from sosreport
	# - having sar collect sysinfo data for topology at tool registration
	# - inspecting data from stockpile
}

sub get_cpu_socket_core {
	my $cpuid = shift;
	my $cpu_ref = shift;
	# with cpuid as the input, return the socket and core ID as an array
	if (defined $$cpu_ref[$cpuid]) {
		return @{ $$cpu_ref[$cpuid] };
	} else {
		return (0, $cpuid);
	};
}

1;
