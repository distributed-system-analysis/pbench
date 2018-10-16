#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-
# Author: Andrew Theurer

package PbenchBase;
use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use JSON;

our @EXPORT_OK = qw(get_json_file put_json_file get_benchmark_names get_clients get_pbench_run_dir get_pbench_install_dir get_pbench_config_dir get_pbench_bench_config_dir get_benchmark_results_dir get_params remove_params remove_element get_hostname get_pbench_datetime);
my $script = "PbenchBase.pm";
my $sub;

sub get_hostname {
	my $hostname = `hostname -s`;
	chomp $hostname;
	return $hostname;
}
sub get_pbench_run_dir {
	my $dir = `getconf.py pbench_run pbench-agent`; # typically /var/lib/pbench-agent
	chomp $dir;
	return $dir;
}
sub get_pbench_install_dir {
	my $dir = `getconf.py install-dir pbench-agent`; # typically /var/lib/pbench-agent
	chomp $dir;
	return $dir;
}
sub get_pbench_config_dir {
	return get_pbench_install_dir() . "/config";
}
sub get_pbench_bench_config_dir {
	return get_pbench_install_dir() . "/config/benchmark";
}
sub get_params { # this simply takes @ARGV-like array and returns a hash with key=argument and value=value
	my %params;
	for my $param (@_) {
		if ($param =~ /--(\S+)=(.+)/) {
			$params{$1} = $2;
		}
	}
	return %params;
}
sub remove_element { # remove first occurrance of value in array
	my $argv_ref = shift; # array to remove element from
	my $val = shift; # the value to search for and remove
	my $index = 0;
	for my $array_val (@{ $argv_ref }) {
		if ($array_val eq $val) {
			splice(@{ $argv_ref }, $index, 1);
			last;
		}
		$index++;
	}
}
sub remove_params { # remove any parameters with "arg"
	my $argv_ref = shift;
	my @args = @_;
	for my $arg (@args) {
		my $index = 0;
		for my $param (@{ $argv_ref }) {
			if ($param =~ /--(\S+)=(\S+)/) {
				if ($1 eq $arg) {
					splice(@{ $argv_ref }, $index, 1);
				}
			}
			$index++;
		}
	}
}
# read a json file and put in hash
# the return value is a reference
sub get_json_file {
	$sub = "get_json()";
	my $filename = shift;
	open(JSON, $filename) || die("$script $sub: could not open file $filename\n");
	my $json_text = "";
	my $junk_mode = 1;
	while ( <JSON> ) {
		if ($junk_mode) {
			if ( /(.*)(\{.*)/ ) { # ignore any junk before the "{"
				$junk_mode = 0;
				my $junk = $1;
				my $not_junk = $2;
				$json_text = $json_text . $not_junk;
			}
		} else {
				$json_text = $json_text . $_;
		}
	}
	close JSON;
	my $perl_scalar = from_json($json_text);
	return $perl_scalar;
}
sub put_json_file {
	my $doc_ref = shift;
	my $filename = shift;
	my $json_text  = to_json($doc_ref, { ascii => 1, pretty => 1, canonical => 1 } );
	open(my $fh, ">" . $filename) || die "$script: could not open file $filename: $!\n";
	print $fh $json_text;
	close($fh);
}
# find all the benchmarks in the pbench configuraton data
# todo: return as an array instead of printing
sub get_benchmark_names {
	$sub = "get_benchmark_names()";
	my $dir = shift;
	my @benchmarks;
	opendir(my $dh, $dir) || die("$script $sub: Could not open directory $dir: $!\n");
	my @entries = readdir($dh);
	for my $entry (grep(!/pbench/, @entries)) {
		if ($entry =~ /^(\w+)\.json$/) {
			#printf "%s\n", $1;
			push(@benchmarks, $1);
		}
	}
	return @benchmarks;
}
# scan the cmdline and return an array of client hostnames in --clients= if present
sub get_clients {
	my @clients;
	for my $param (@_) {
		if ($param =~ /\-\-clients\=(.+)/) {
			@clients = split(/,/, $1);
		}
	}
	return @clients;
}
sub get_pbench_datetime { #our common date & time forma
	my $datetime = `date --utc +"%Y.%m.%dT%H.%M.%S"`;
	chomp $datetime;
	return $datetime;
}
# get a new benchmark directory -needed if you are going to run a benchmark
sub get_benchmark_results_dir {
	my $benchmark = shift;
	my $config = shift;
	my $basedir = get_pbench_run_dir();
	my $datetime = get_pbench_datetime();
	my $benchdir = $basedir . "/" . $benchmark . "_" . $config . "_" . $datetime;
}

1;
