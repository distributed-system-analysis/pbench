#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-
# Author: Andrew Theurer

package PbenchCDM;
use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use JSON;

our @EXPORT_OK = qw(create_run_doc create_config_osrelease_doc create_config_cpuinfo_doc create_config_netdevs_doc create_config_ethtool_doc);
my $script = "PbenchCDM.pm";
my $sub;
my @common_run_fields = qw(run_id run_user_name run_user_email run_controller_hostname run_benchmark_name
			   run_benchmark_ver run_benchmark_params run_benchmark_hosts run_benchmark_hosts_clients
			   run_benchmark_hosts_servers);

sub get_uuid {
	my $uuid = `uuidgen`;
	chomp $uuid;
	return $uuid;
}
sub get_user_name { # looks for USER_NAME in %ENV
	if ($ENV{"USER_NAME"}) {
		return $ENV{"USER_NAME"}
	}
}
sub get_user_email { # looks for USER_NAME in %ENV
	if ($ENV{"USER_EMAIL"}) {
		return $ENV{"USER_EMAIL"};
	}
}
sub get_proc_cmdline {
	my $proc_cmdline = `cat /proc/cmdline`;
	chomp $proc_cmdline;
	return $proc_cmdline;
}
sub check_file {
	my $filename = shift;
	my $regex = shift;
	open(my $fh, "<" . $filename);
	while (<$fh>) {
		if (/$regex/) {
			return $1;
		}
	}
}
sub get_hostname {
	#return (chomp(my $hostname = `hostname -s`));
	my $hostname = `hostname -s`;
	chomp $hostname;
	return $hostname;
}
sub create_run_doc {
	my $benchmark = shift;
	my $config = shift;
	return (
		# fields every single doc needs
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# the run-specific fields
		"run_id" => get_uuid, # unique identifier for this run
		"user_config" => $config, # user provided shortlist of var:val with "," separator (no spaces)
		"user_name" => get_user_name, # user's real name
		"user_email" => get_user_email, #user's email address
		"run_hostname" => get_hostname, # hostname of this controller system
		"benchmark_name" => $benchmark, #the benchmark used in this run
		"benchmark_ver" => "", #benchmark version, like "3.7" for fio
		"benchmark_params" => "", # the full list of parameters when calling the benchmark
		"benchmark_hosts" => "", # any/all hosts involved in the benchmark
		"benchmark_hosts_clients" => "", # client hosts involved in the benchmark
		"benchmark_hosts_servers" => "", # server hosts involved in the benchmark
		"benchmark_num_iterations" => "",
		"benchmark_iteration_list" => "", # a list of every iteration, where each iteration is all of the parameters (arg=val)
		# links to config docs
		"config_hostnames" => "ordered list of hostnames where configuration docs are generated from", # 
		"config_collectors" => "ordered list (matching order of config_hostnames) of config-collectors where configuration docs are generated from", # 
		"config_doc_ids" => "ordered list of document IDss where configuration docs are generated from", # 
		# links to tools
		"tool_hostnames" => "ordered list of hostnames where tools are registred", # 
		"tool_names" => "ordered list (matching order of tool_hostnames) of registered tool names" # 
	       );
}
# this is a 1-doc config source
sub create_config_osrelease_doc { # /etc/os-release
	my %config_osrelease_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run
		"run_id" => "",
		# always include the hostname
		"hostname" => get_hostname # hostname where info came from
		);
	open (my $fh, "</etc/os-release");
	for my $line (<$fh>) {
		if ($line =~ /^(\S+)=\"(.+)\"$/) {
			$config_osrelease_doc{$1} = $2;
		}
	}
	return %config_osrelease_doc;
}
# this is a 1-doc config source
sub create_config_cpuinfo_doc { # /bin/lscpu: cpu model, speed, flags, etc
	my %config_cpuinfo_doc;
	my @output = split(/\n/, `lscpu`);
	for my $line (@output) {
		(my $field, my $value) = split(/:/, $line);
		$field =~ s/\(s\)/s/g;
		$field =~ s/\s+/_/g;
		$value =~ s/^\s+//;
		$config_cpuinfo_doc{$field} = $value;
	}
	return %config_cpuinfo_doc
}
# this is a multi-doc config source
sub create_config_netdevs_doc {
	my %config_netdevs_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run
		"run_id" => "",
		# always include the hostname
		"hostname" => get_hostname # hostname where info came from
		);
	($config_netdevs_doc{"netdevs_list"} = `/bin/ls /sys/class/net`) =~ s/\s+/,/g;
	return %config_netdevs_doc;
}
# this document is per-netdev, and it linked to the config_netdevs_doc collected on the same host
sub create_config_ethtool_doc {
	my $netdev = shift;
	my $netdev_doc_id = shift;
	my %config_ethtool_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run
		"run_id" => "",
		# always include the hostname
		"hostname" => get_hostname, # hostname where info came from
		# include the netdevs doc ID
		"netdevs_id" => $netdev_doc_id
		);
	for my $opt qw(-a -c -g -i -k ) {
		my $ethtool_cmd = "/usr/sbin/ethtool " . $opt . " " . $netdev;
		printf "ethtool_cmd[$ethtool_cmd]\n";
		my @output = split(/\n/, `$ethtool_cmd`);
		for my $line (@output) {
			if ($line =~ /^\s*(\S+):\s*(.+)/) {
				$config_ethtool_doc{$1} = $2;
			}
		}
	}
	# ethtool with no opts needs special formatting
	my $ethtool_cmd = "/usr/sbin/ethtool " . $netdev;
	my @output = split(/\n/, `$ethtool_cmd`);
	shift @output; #get rid of first line
	my $current_field;
	for my $line (@output) {
		# this ethtool output has optional multi-line output for each feature
		$line =~ s/\s+$//;
		# this matches the first line
		if ($line =~ /^[\t\s]+(.+):[\t\s]*(.+)\t*$/) {
			$config_ethtool_doc{$1} = $2;
			$current_field = $1; # remember the field name in case there is a second line
		} else {
			# this will match the special second line, where the feature name is not in that line
			if ($line =~ /^[\t\s]*(.+)[\t\s]*$/ and $current_field) {
				$config_ethtool_doc{$current_field} .= "," . $1;
			}
		}
	}
	return %config_ethtool_doc;
}
1;
