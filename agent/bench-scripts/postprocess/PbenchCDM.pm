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

our @EXPORT_OK = qw(create_run_doc);
my $script = "PbenchCDM.pm";
my $sub;
my @common_run_fields = qw(run_id run_user_name run_user_email run_controller_hostname run_benchmark_name
			   run_benchmark_ver run_benchmark_params run_benchmark_hosts run_benchmark_hosts_clients
			   run_benchmark_hosts_servers);

sub get_uuid {
	 return `uuidgen`;
}

sub get_user_name { # looks for USER_NAME in %ENV
	if ($ENV{"USER_NAME"}) {
		return $ENV{"USER_NAME"}
	}
}
sub get_user_email { # looks for USER_NAME in %ENV
	if ($ENV{"USER_EMAIL"}) {
		return $ENV{"USER_EMAIL"}
	}
}

sub get_proc_cmdline {
	my $proc_cmdline = `cat /proc/cmdline`;
	chomp $proc_cmdline;
	return $proc_cmdline;
}

sub create_run_doc {
	my $benchmark = shift;
	my $config = shift;
	return ( # unless otherwise noted the values are strings
		 "doc_id" => get_uuid, # uniqie identifier for all documents
		 "doc_ver" => 1, # common-data-model version number
		# the run-specific fields
		 "run_id" => get_uuid, # unique identifier for this run
		 "run_testconfig" => $config, # user provided shortlist of var:val with "," separator (no spaces)
		 "run_user_name" => get_user_name, # user's real name
		 "run_user_email" => get_user_email, #user's email address
		 "run_controller_hostname" => `hostname -s`, # hostname of this controller system
		 "run_config_doc_ids" => "", # the "doc_id" value in the benchmark CDM document
		 "run_benchmark_name" => $benchmark, #the benchmark used in this run
		 "run_benchmark_ver" => "", #benchmark version, like "3.7" for fio
		 "run_benchmark_params" => "", # the full list of parameters when calling the benchmark
		 "run_benchmark_hosts" => "", # any/all hosts involved in the benchmark
		 "run_benchmark_hosts_clients" => "", # client hosts involved in the benchmark
		 "run_benchmark_hosts_servers" => "", # server hosts involved in the benchmark
		 "run_hosts_hostnames" => "", # any host involved in this test in any capacity
		 "run_num_iterations" => "",
		 "run_iteration_list" => "", # a list of every iteration, where each iteration is all of the parameters (arg=val)
		# the config-specific fields
		 "run_hosts_vulnerabilities" => "", # list of any active vulnerabilities found in all hosts involved
		 "run_hosts_perhost_vulnerabilities" => "", # list of hostname1:vulnerability1:vulnerability2,hostname2:vulnerability1:vulnerability2
		 "run_hosts_mitigations" => "", # list of any active mititgations found in all hosts involved
		 "run_hosts_perhost_mititgations" => "", # list of hostname1:mitigation1,mitigation2,hostname2:mitigation1:mitigation2
		 # the osrelease values come from /etc/osrelease
		 "run_controller_osrelease_name" => "", # ex: "Red Hat Enterprise Linux Server"
		 "run_controller_osrelease_id" => "", # ex: "rhel"
		 "run_controller_osrelease_ver_id" => "", # ex: "7.6"
		 "run_controller_osrelease_pretty_name" => "", # ex: "Red Hat Enterprise Linux Server 7.6 Beta (Maipo)"
		 "run_controller_proc_cmdline" => get_proc_cmdline # 
	       );
}
sub create_config_doc { # the primary config doc for each host, specific collectors for this host "link" to this doc
	my $config_source = shift;
	my $config_hostname = shift;
	my $run_doc_ref = shift;
	my %config_doc = (
			 "doc_id" => get_uuid, # uniqie identifier for all documents
			 "doc_ver" => 1, # common-data-model version number
			 "config_id" => get_uuid, # unique identifier for this run
			 "config_hostname" => $config_hostname, # this indicates which host the config collectors where run on
			 "config_collectors" => "", # a list of collectors that were run (on the same config_hostname) and their doc_id, like: cpuinfo:<doc_id>,dmidecode:<doc_id>, 
			);
	 # common terms coming from run document
	 for my $field (@common_run_fields) {
		$config_doc{$field} = $$run_doc_ref{$field};
	}
}
sub create_config_cpuinfo_doc {

}

1;
