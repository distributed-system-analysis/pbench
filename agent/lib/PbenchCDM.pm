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

our @EXPORT_OK = qw(create_run_doc create_config_osrelease_doc create_config_cpuinfo_doc create_config_netdevs_doc create_config_ethtool_doc create_config_base_doc get_hostname get_uuid create_bench_iter_sample_doc create_metric_sample_doc create_metric_sample_doc create_bench_iter_sample_period_doc create_bench_iter_doc);
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
sub get_hostname {
	my $hostname = `hostname -s`;
	chomp $hostname;
	return $hostname;
}
sub populate_base_fields { # create the fields every doc must have
	my $doc_ref = shift;
	$$doc_ref{'doc_id'} = get_uuid;
	$$doc_ref{'ver'} = 1;
}
sub copy_doc_fields {
	my $copy_from_ref = shift; # what document we need to copy from
	my $copy_to_ref = shift; # what new document we're copying to
	my $replace_doc_id_name_with = shift; # take doc_id from copy-from doc and transform it for copy-to doc
	for my $field_name (grep(!/doc_id|doc_ver|doc_create_time/, keys %$copy_from_ref)) {
		$$copy_to_ref{$field_name} = $$copy_from_ref{$field_name};
	}
	if ($replace_doc_id_name_with) {
		$$copy_to_ref{$replace_doc_id_name_with} = $$copy_from_ref{'doc_id'};
	}
}
sub create_run_doc {
	my %doc;
	populate_base_fields(\%doc);
	$doc{'bench_name'} = shift;
	$doc{'bench_params'} = shift; # the full list of parameters when calling the benchmark
	$doc{'bench_hosts_clients'} = shift; # client hosts involved in the benchmark
	$doc{'bench_hosts_servers'} = shift; # server hosts involved in the benchmark
	$doc{'user_desc'} = shift; # user provided shortlist of var:val with "," separator (no spaces)
	$doc{'user_name'} = shift; # user's real name
	$doc{'user_email'} = shift; #user's email address
	$doc{'tool_hostnames'} = shift; # ordered list of hostnames where tools are registred
	$doc{'tool_names'} = shift; # ordered list (matching order of tool_hostnames) of registered tool names
	$doc{'hostname'} = get_hostname; # hostname of this controller system
	return %doc;
}
sub create_bench_iter_doc { # document describing the benchmark iteraton sample
	my %doc;
	populate_base_fields(\%doc);
	copy_doc_fields(shift, \%doc, 'run_id'); # get some essential fields from iter-sample, our first arg
	$doc{'bench_params'} = shift; # second arg is benchmark parameters for this iter
	return %doc;
}
sub create_bench_iter_sample_doc { # document describing the benchmark iteraton sample
	my %doc;
	populate_base_fields(\%doc);
	copy_doc_fields(shift, \%doc, 'iter_id'); # get some essential fields from iter doc, our first arg
	$doc{'sample_num'} = shift; # second arg is sample number (just used to make it obvious which order these occur in)
	return %doc;
}
sub create_bench_iter_sample_period_doc { # document describing the benchmark iteraton sample
	my %doc;
	populate_base_fields(\%doc);
	copy_doc_fields(shift, \%doc, 'sample_id'); # get some essential fields from iter-sample doc, our first arg
	$doc{'name'} = shift; # second arg is period name
	$doc{'prev_period_doc_id'} = shift; # third arg is link to prev period in this sample, if any
	return %doc;
}
sub create_metric_sample_doc { # document describing the benchmark iteraton sample
	my %doc;
	populate_base_fields(\%doc);
	copy_doc_fields(shift, \%doc, 'period_id'); # get some essential fields from iter-sample-period doc, our first arg
	# These are the required fields for any metric-instance-sample.  There are potentially
	# more fields, but not all metrics use all the same options fields.  However, the ones
	# below must all be used, and so creating a new doc requires that these fields be
	# defined.
	$doc{'class'} = shift; # "throughput" (work over time, like Gbps or interrupts/sec) or "count" (quantity, percent, sum, elapsed time, value, etc)
	$doc{'type'} = shift; # A generic name for this metric, like "gigabits-per-second", does not include specifics like "/dev/sda" or "cpu1"
	$doc{'hostname'} = shift; # the hostname where this metric comes from
	$doc{'source'} = shift; # a benchmark or tool where this metric comes from, like "iostat" or "fio"
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
	$doc{'name_format'} = shift;
	$doc{'value'} = shift; # the value of the metric
	$doc{'timestamp'} = shift; # the epochtime
	# Optional fields will be validated with a different function, likely at the
	# time the document is written to a file.  A list of optional fields needs
	# to be maintained.  ES docs typically cannot have more than 1000 fields,
	# which for metrics, should be fine, but we should track these so we don't
	# introduce unknown fields into ES.
	return %doc;
}
1;
