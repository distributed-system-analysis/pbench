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
use PbenchAnsible qw(ssh_hosts ping_hosts copy_files_to_hosts copy_files_from_hosts remove_files_from_hosts remove_dir_from_hosts create_dir_hosts sync_dir_from_hosts verify_success);

our @EXPORT_OK = qw(create_run_doc create_config_osrelease_doc create_config_cpuinfo_doc create_config_netdevs_doc create_config_ethtool_doc create_config_base_doc get_hostname get_uuid create_bench_iter_sample_doc create_metric_sample_doc create_metric_sample_doc create_bench_iter_sample_period create_bench_iter_doc);
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
	return (
		# fields every single doc needs
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# the run-specific fields
		"user_config" => "", # user provided shortlist of var:val with "," separator (no spaces)
		"user_name" => "", # user's real name
		"user_email" => "", #user's email address
		"run_hostname" => get_hostname, # hostname of this controller system
		"benchmark_name" => $benchmark, #the benchmark used in this run
		"benchmark_params" => "", # the full list of parameters when calling the benchmark
		"benchmark_hosts_all" => "", # any/all hosts involved in the benchmark (not just clients and servers)
		"benchmark_hosts_clients" => "", # client hosts involved in the benchmark
		"benchmark_hosts_servers" => "", # server hosts involved in the benchmark
		"benchmark_num_iterations" => "",
		"benchmark_iterations" => "", # a list of every iteration, where each iteration is all of the parameters (arg=val)
		# links to config docs
		"config_hostnames" => "", # ordered list of hostnames where a config base document was created for that host
		"config_doc_ids" => "", # ordered list (matching order of hostnames in config_hostnames) of config base document IDs
		# links to tools
		"tool_hostnames" => "", # ordered list of hostnames where tools are registred
		"tool_names" => "" # ordered list (matching order of tool_hostnames) of registered tool names
	       );
}
sub create_bench_iter_doc { # document describing the benchmark iteraton sample
	my $benchmark = shift;
	my $run_id = shift;
	my $bench_params = shift;
	my $bench_hosts_clients = shift;
	my $bench_hosts_servers = shift;
	return (
		# fields every single doc needs
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		"run_id" => $run_id, # pointer to run document
		"benchmark_name" => $benchmark, #the benchmark used in this run
		"benchmark_params" => $bench_params, # the full list of parameters when calling the benchmark
		"benchmark_hosts_clients" => $bench_hosts_clients, # client hosts involved in the benchmark
		"benchmark_hosts_servers" => $bench_hosts_servers # server hosts involved in the benchmark
	       );
}
sub create_bench_iter_sample_doc { # document describing the benchmark iteraton sample
	my $benchmark = shift;
	return (
		# fields every single doc needs
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		"run_id" => "", # pointer to run document
		"benchmark_name" => $benchmark, #the benchmark used in this run
		"benchmark_params" => "", # the full list of parameters when calling the benchmark
		"benchmark_hosts_clients" => "", # client hosts involved in the benchmark
		"benchmark_hosts_servers" => "" # server hosts involved in the benchmark
	       );
}
sub create_bench_iter_sample_period {
	my $run_id = shift; # pointer to run document
	my $iteration_id = shift; # pointer to iteration document
	my $sample_id = shift; # pointer to sample document
	my $measurment_period_type = shift;
	return (
		# fields every single doc needs
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		"run_id" => $run_id, # pointer to run document
		"iteration_id" => $iteration_id, # pointer to the bencmark-iteration doc
		"sample_id" => $sample_id # pointer to benchmark-iteration-sample doc
	);
}
sub create_metric_sample_doc { # document describing the benchmark iteraton sample
	# These are the required fields for any metric-instance-sample.  There are potentially
	# more fields, but not all metrics use all the same options fields.  However, the ones
	# below must all be used, and so creating a new doc requires that these fields be
	# defined.
	my $run_id = shift; # pointer to run document
	my $iteration_id = shift; # pointer to benchmark-iteration document
	my $sample_id = shift; # pointer to benchmark-iteration-sample document
	my $period_id = shift; # pointer to time period in benchmark sample (or nothing if not associated with specific period)
	my $class = shift; # "throughput" (work over time, like Gbps or interrupts/sec) or "count" (quantity, percent, sum, elapsed time, value, etc)
	my $type = shift; # A generic name for this metric, like "gigabits-per-second", does not include specifics like "/dev/sda" or "cpu1"
	my $hostname = shift; # the hostname where this metric comes from
	my $source = shift; # a benchmark or tool where this metric comes from, like "iostat" or "fio"
	# The instance_name_format tells us how the name for this metric-instance is assembled.
	# The instance name is assembled from other fields in this document
	# the format is described by joining strings and field names (which are identified by % before and after), like:
	#     network-L2-%type%-%hostname%,
	#         where type=Gbps and hostname=perf1,
	#         so this resolves to:
	#     network-L2-Gbps-perf1
	# or: %source%-%bin%-%pid%/%tid%-%hostname%-percent-cpu-usage,
	#         where source=pidstat, bin=qemu pid=1094 tid=1095 hostname=perf1
	#         so this resolves to: 
	#     pidstat-qemu-1094/1095-perf1-percent-cpu-usage
	# It is vitally important that the metric-instance name use enough fields
	# so that the resulting name is different from any other metric-instance.
	# For example, you want to ensure that the pidstat data from host perf1
	# does not have the exact same metric-instance name as pidstat data from
	# host perf2, and so including %hostname% in a metric-instance name
	# format is almost always required.  However, there are potneitally many
	# more fields required, and this code can't possibly know all situations
	# so it is up to the caller of this function to understand that scenario
	# and provide an adequtate instance name format.
	my $instance_name_format = shift;
	my $value = shift; # the value of the metric
	my $timestamp = shift; # the epochtime
	return (
		# fields every single doc needs
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		"run_id" => $run_id, # pointer to run document
		"sample_id" => $sample_id,
		"period_id" => $period_id,
		"class" => $class,
		"type" => $type,
		"hostname" => $hostname,
		"source" => $source,
		"name_format" => $instance_name_format,
		"value" => $value,
		"timestamp" => $timestamp
	       );
	# Optional fields will be validated with a different function, like at the
	# time the document is written to a file.  A list of optional fields needs
	# to be maintained.  ES docs typically cannot have more than 1000 fields,
	# which for metrics, should be fine, but we should track these so we don't
	# introduce unknown fields into ES.
}
# this is the top-level config doc for a host
sub create_config_base_doc {
	my $run_id = shift;
	my %config_base_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run document
		"run_id" => $run_id,
		# always include the hostname
		"hostname" => get_hostname # hostname where info came from
		"config_source_names" => "", # orderd list of config sources, like osrelease, cpuinfo, or netdevs
		"config_source_doc_ids" => "", # orderd list of config document IDs, matching order of config_sources_list
		);
}
# this is a 1-doc config source
sub create_config_osrelease_doc { # /etc/os-release
	my $run_id = shift;
	my %config_osrelease_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run
		"run_id" => $run_id,
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
	my $run_id = shift;
	my %config_cpuinfo_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run
		"run_id" => $run_id,
		# always include the hostname
		"hostname" => get_hostname # hostname where info came from
		);
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
	my $run_id = shift;
	my %config_netdevs_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run
		"run_id" => $run_id,
		# always include the hostname
		"hostname" => get_hostname, # hostname where info came from
		"ethtool_doc_ids" => "" # an ordered list (matching order of "netdevs") of the ethtool document IDs
		);
	($config_netdevs_doc{"netdevs"} = `/bin/ls /sys/class/net`) =~ s/\s+/,/g;
	return %config_netdevs_doc;
}
# this document is per-netdev, and it linked to the config_netdevs_doc collected on the same host
sub create_config_ethtool_doc {
	my $netdev = shift;
	my $netdev_doc_id = shift;
	my $run_id = shift;
	my %config_ethtool_doc = (
		# every document needs these three:
		"doc_id" => get_uuid, # uniqie identifier for all documents
		"doc_ver" => 1, # common-data-model version number
		"doc_create_time" => "" ,# the epoch time when creatd *in-elastic*, not here
		# always link back to run
		"run_id" => $run_id,
		# always include the hostname
		"hostname" => get_hostname, # hostname where info came from
		# include the netdevs doc ID
		"netdev_id" => $netdev_doc_id
		);
	for my $opt (qw(-a -c -g -i -k )) {
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
