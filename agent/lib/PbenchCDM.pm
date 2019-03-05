#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 4 -*-
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=perl
# Author: Andrew Theurer

package PbenchCDM;
use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use JSON;
use PbenchAnsible    qw(ssh_hosts ping_hosts copy_files_to_hosts copy_files_from_hosts
                        remove_files_from_hosts remove_dir_from_hosts create_dir_hosts
                        sync_dir_from_hosts verify_success);
use PbenchBase       qw(get_hostname get_pbench_datetime);

our @EXPORT_OK = qw(create_run_doc create_config_osrelease_doc create_config_cpuinfo_doc
                    create_config_netdevs_doc create_config_ethtool_doc create_config_base_doc
                    get_uuid create_bench_iter_sample_doc create_metric_sample_doc
                    create_metric_sample_doc create_bench_iter_sample_period_doc
                    create_bench_iter_doc create_config_doc get_cdm_ver);

my $script = "PbenchCDM.pm";
my $sub;

sub get_cdm_ver {
    return 'v3dev';
}

sub get_uuid {
    my $uuid = `uuidgen`;
    chomp $uuid;
    return $uuid;
}

sub get_user_name { # Looks for USER_NAME in %ENV
    if (exists $ENV{"USER_NAME"}) {
        return $ENV{"USER_NAME"}
    }
}

sub get_user_email { # Looks for USER_NAME in %ENV
    if (exists $ENV{"USER_EMAIL"}) {
        return $ENV{"USER_EMAIL"};
    }
}

# Create the fields every doc must have
sub populate_base_fields {
    my $doc_ref = shift;
    $$doc_ref{'cdm'}{'ver'} = get_cdm_ver;
}

sub copy_doc_fields {
    my $copy_from_ref = shift; # What document we need to copy from
    my $copy_to_ref = shift; # What new document we're copying to
    %$copy_to_ref = %$copy_from_ref;
    undef $$copy_to_ref{'cdm'};
}

# Create a document with all of the run information
sub create_run_doc {
    my %doc;
    populate_base_fields(\%doc);
    $doc{'run'}{'bench'}{'name'} = shift; # Name of the actual benchmark used, like fio ir uperf
    $doc{'run'}{'bench'}{'params'} = shift; # Full list of parameters when calling the benchmark
    $doc{'run'}{'bench'}{'clients'} = shift; # Client hosts involved in the benchmark
    $doc{'run'}{'bench'}{'servers'} = shift; # Server hosts involved in the benchmark
    $doc{'run'}{'user'}{'desc'} = shift; # User provided test description
    $doc{'run'}{'user'}{'tags'} = shift; # User provided tags like, "beta,project-X"
    $doc{'run'}{'user'}{'name'} = shift; # User's real name
    $doc{'run'}{'user'}{'email'} = shift; # User's email address
    $doc{'run'}{'harness_name'} = shift; # Harness name like pbench, browbeat, cbt
    $doc{'run'}{'tool_names'} = shift; # List tool names like sar, mpstat
    $doc{'run'}{'host'} = get_hostname; # Hostname of this controller system
    $doc{'run'}{'ignore'} = JSON::false; # Set to true later if run should be ingnored in queries
    $doc{'run'}{'start'} = time * 1000;
    $doc{'run'}{'id'} = get_uuid;
    $doc{'cdm'}{'doctype'} = 'run';
    return %doc;
}

# Create a document describing a configuration source
sub create_config_doc {
    my $copy_from_ref = shift; # first arg is a reference to a doc
                               # (like the run doc) we copy info from
    my $config_ref = shift;    # second arg is hash reference to any other
                               # keys/values to include in this doc
    my %doc;
    copy_doc_fields($copy_from_ref, \%doc); # get some essential fields from another doc (like run)
    populate_base_fields(\%doc);
    $doc{'cdm'}{'doctype'} = "config_" . $$config_ref{'module'};
    $doc{'config'}{'id'} = get_uuid;
    for my $key (keys %$config_ref) {
        if ($key =~ /^host$|^module$|^source_type$|^scribe_uuid$/) {
            $doc{'config'}{$key} = $$config_ref{$key};
        } else {
            $doc{'config'}{$$config_ref{'module'}}{$key} = $$config_ref{$key};
        }
    }
    return %doc;
}

# Create a document describing the benchmark iteraton
# The benchmark iteration represents the benchmark configuration (parameters, hosts, etc).
# Typically, within a run, each iteration represents a unique set of parameters, where
# at least one --arg or value is different from another parameter.
sub create_bench_iter_doc {
    my %doc;
    copy_doc_fields(shift, \%doc); # Get some essential fields from iter-sample, our first arg
    populate_base_fields(\%doc);
    $doc{'iteration'}{'params'} = shift; # Second arg is benchmark parameters for this iter
    $doc{'iteration'}{'id'} = get_uuid;
    $doc{'cdm'}{'doctype'} = 'iteration';
    return %doc;
}

# Create a document describing the benchmark iteraton sample
# A sample is a single execution of a benchmark iteration
# Multiple samples have the exact same benchmark parameters
sub create_bench_iter_sample_doc {
    my %doc;
    copy_doc_fields(shift, \%doc); # Get some essential fields from iter doc, our first arg
    populate_base_fields(\%doc);
    $doc{'sample'}{'num'} = shift; # Second arg is sample number
    $doc{'sample'}{'id'} = get_uuid;
    $doc{'cdm'}{'doctype'} = 'sample';
    return %doc;
}

# Create a document describing the benchmark iteraton sample period
# A period is a length of time in the benchmark execution representing
# a certain action, like "warmup", "measurement", or "cool-down".
# All benchmarks must have at least 1 period, a "measurement" period
sub create_bench_iter_sample_period_doc {
    my %doc;
    copy_doc_fields(shift, \%doc); # Get some essential fields from iter-sample doc, our first arg
    populate_base_fields(\%doc);
    $doc{'period'}{'name'} = shift; # Second arg is period name
    $doc{'period'}{'prev_id'} = shift; # Third arg is link to prev period in this sample, if any
    $doc{'period'}{'id'} = get_uuid;
    $doc{'cdm'}{'doctype'} = 'period';
    return %doc;
}

# Create a document describing either a benchmark or tool metric (result)
sub create_metric_sample_doc {
    my %doc;
    copy_doc_fields(shift, \%doc); # Get some essential fields from a prev doc, our first arg
    populate_base_fields(\%doc);
    $doc{'cdm'}{'doctype'} = 'metric';
    # These are the required fields for any metric.  There are potentially
    # more fields, but not all metrics use all the same options fields.  However, the ones
    # below must all be used, and so creating a new doc requires that these fields be
    # defined.
    $doc{'metric'}{'class'} = shift; # "throughput" (work over time, like Gbps or interrupts/sec) or
                                     # "count" (quantity, percent, sum, elapsed time, value, etc)
    $doc{'metric'}{'type'} = shift; # A generic name for this metric, like "gigabits-per-second",
                                    # does not include specifics like "/dev/sda" or "cpu1"
    $doc{'metric'}{'host'} = shift; # The hostname where this metric comes from
    $doc{'metric'}{'source'} = shift; # A benchmark or tool where this metric comes from, like
                                      # "iostat" or "fio"
    # The instance_name_format tells us how the name for this metric-instance is assembled.
    # The instance name is assembled from other fields in this document
    # the format is described by joining strings and field names
    # (which are identified by % before and after), like:
    #
    #     network-L2-%type%-%host%,
    #         where type=Gbps and host=perf1,
    #         so this resolves to:
    #     network-L2-Gbps-perf1
    #
    # or: %source%-%bin%-%pid%/%tid%-%host%-percent-cpu-usage,
    #         where source=pidstat, bin=qemu pid=1094 tid=1095 host=perf1
    #         so this resolves to: 
    #     pidstat-qemu-1094/1095-perf1-percent-cpu-usage
    #
    # It is vitally important that the metric-instance name use enough fields
    # so that the resulting name is different from any other metric-instance.
    # For example, you want to ensure that the pidstat data from host perf1
    # does not have the exact same metric-instance name as pidstat data from
    # host perf2, and so including %host% in a metric-instance name
    # format is almost always required.  However, there are potneitally many
    # more fields required, and this code can't possibly know all situations
    # so it is up to the caller of this function to understand that scenario
    # and provide an adequtate instance name format.
    $doc{'metric'}{'name_format'} = shift;
    $doc{'metric'}{'value'} = shift; # The value of the metric
    $doc{'metric'}{'end'} = shift; # The end epochtime for this value.  A 'begin' epochtime
                                   # can also be used if you have one.  Using both is the best
                                   # way to represent a metric which was actually an avergae
                                   # over a (begin-to-end) time-period.  If you only have a single
                                   # metric for an entire period, it is highly recommened both
                                   # begin and end are used.
    $doc{'metric'}{'id'} = get_uuid;
    # Optional fields will be validated with a different function, likely at the
    # time the document is written to a file.  A list of optional fields needs
    # to be maintained.  ES docs typically cannot have more than 1000 fields,
    # which for metrics, should be fine, but we should track these so we don't
    # introduce unknown fields into ES.
    return %doc;
}
1;
