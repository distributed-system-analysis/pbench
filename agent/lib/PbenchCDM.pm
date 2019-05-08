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
use Data::Dumper;
use PbenchAnsible    qw(ssh_hosts ping_hosts copy_files_to_hosts copy_files_from_hosts
                        remove_files_from_hosts remove_dir_from_hosts create_dir_hosts
                        sync_dir_from_hosts verify_success);
use PbenchBase       qw(get_hostname get_pbench_datetime get_json_file);

our @EXPORT_OK = qw(create_run_doc create_config_osrelease_doc create_config_cpuinfo_doc
                    create_config_netdevs_doc create_config_ethtool_doc create_config_base_doc
                    get_uuid create_bench_iter_sample_doc create_metric_desc_doc
                    create_metric_data_doc create_bench_iter_sample_period_doc
                    create_bench_iter_doc create_config_doc get_cdm_ver get_cdm_rel
                    log_cdm_metric_sample gen_cdm_metric_data);

my $script = "PbenchCDM.pm";
my $condense_samples = 1;

sub get_cdm_ver {
    return 4;
}

sub get_cdm_rel {
    return "dev"; # can also be "prod"
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
    $$doc_ref{'cdm'}{'ver'} = int get_cdm_ver;
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
    $doc{'run'}{'bench'}{'clients'} =~ s/,/ /g;
    $doc{'run'}{'bench'}{'servers'} = shift; # Server hosts involved in the benchmark
    $doc{'run'}{'bench'}{'servers'} =~ s/,/ /g;
    $doc{'run'}{'user'}{'desc'} = shift; # User provided test description
    $doc{'run'}{'user'}{'tags'} = shift; # User provided tags like, "beta,project-X"
    $doc{'run'}{'user'}{'tags'} =~ s/,/ /g;
    $doc{'run'}{'user'}{'name'} = shift; # User's real name
    $doc{'run'}{'user'}{'email'} = shift; # User's email address
    $doc{'run'}{'harness_name'} = shift; # Harness name like pbench, browbeat, cbt
    $doc{'run'}{'tool_names'} = shift; # List tool names like sar, mpstat
    $doc{'run'}{'tool_names'} = s/,/ /g;
    $doc{'run'}{'host'} = get_hostname; # Hostname of this controller system
    $doc{'run'}{'ignore'} = JSON::false; # Set to true later if run should be ingnored in queries
    $doc{'run'}{'begin'} = int time * 1000;
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
sub create_metric_desc_doc {
    my %doc;
    #copy_doc_fields(shift, \%doc); # Get some essential fields from a prev doc, our first arg
    my $period_doc_ref = shift;
    $doc{'run'}{'id'} = $$period_doc_ref{'run'}{'id'};
    $doc{'iteration'}{'id'} = $$period_doc_ref{'iteration'}{'id'};
    $doc{'period'}{'id'} = $$period_doc_ref{'period'}{'id'};
    $doc{'sample'}{'id'} = $$period_doc_ref{'sample'}{'id'};
    populate_base_fields(\%doc);
    $doc{'cdm'}{'doctype'} = 'metric_desc';
    # These are the required fields for any metric.  There are potentially
    # more fields, but not all metrics use all the same options fields.  However, the ones
    # below must all be used, and so creating a new doc requires that these fields be
    # defined.
    $doc{'metric_desc'}{'class'} = shift; # "throughput" (work over time, like Gbps or interrupts/sec) or
                                     # "count" (quantity, percent, sum, elapsed time, value, etc)
    $doc{'metric_desc'}{'type'} = shift; # A generic name for this metric, like "gigabits-per-second",
                                    # does not include specifics like "/dev/sda" or "cpu1"
    $doc{'metric_desc'}{'source'} = shift; # A benchmark or tool where this metric comes from, like
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
    $doc{'metric_desc'}{'name_format'} = shift;
    $doc{'metric_desc'}{'id'} = get_uuid;
    return %doc;
}
sub create_metric_data_doc {
    my %doc;
    $doc{'metric_data'}{'id'} = shift; # The same id as the metric_desc
    $doc{'metric_data'}{'value'} = shift; # The value of the metric
    $doc{'metric_data'}{'begin'} = int shift; # The begin epochtime for this value.
    $doc{'metric_data'}{'end'} = int shift; # The end epochtime for this value.
    $doc{'metric_data'}{'duration'} = $doc{'metric_data'}{'end'} -
                                      $doc{'metric_data'}{'begin'} + 1;
    return %doc;
}
sub log_cdm_metric_sample {
    my $metric_source = shift;
    my $metric_class = shift;
    my $metric_type = shift;
    my $metric_name_format = shift;
    my $names_ref = shift; # contains all field names used in metric_name_format
    my $metric_ref = shift; # the metric hash we are populating
    my $timestamp_ms = shift;
    my $value = shift;
    my $metric_interval = shift; # the time in ms between each sample is logged
    my $label = $metric_source . "-" . $metric_type . "-";
    # Extract the fiel names from name_format to create the label
    my $tmp_name_format = $metric_name_format;
    while ($tmp_name_format =~ s/([^%]*)%([^%]*)%(\S*$)/$3/) {
        my $prefix = $1;
        my $name = $2;
        my $remainder = $3;
        if (not defined $$names_ref{$name}) {
            print "Error: field name $name not defined\n";
            print "prefix: [$prefix]\n";
            print "field_name: [$name]\n";
            print "remainder: [$remainder]\n";
            print "metric_source: [$metric_source]\n";
            print "metric_type: [$metric_type]\n";
            print "field names:\n";
            print Dumper $names_ref;
            return 1;
        }
        $label .= $prefix . $$names_ref{$name};
    }
    # This only happens when logging the first sample for a metric
    if (not exists $$metric_ref{$label}) {
        #print "creating label: $label metric_type: $metric_type metric_name_format: $metric_name_format\n";
        for my $name (keys %{ $names_ref }) {
            $$metric_ref{$label}{'names'}{$name} = $$names_ref{$name};
        }
        $$metric_ref{$label}{'source'} = $metric_source;
        $$metric_ref{$label}{'class'} = $metric_class;
        $$metric_ref{$label}{'type'} = $metric_type;
        $$metric_ref{$label}{'name_format'} = $metric_name_format;
        if (defined $metric_interval) {
            $$metric_ref{$label}{'interval'} = $metric_interval;
        }
    }
    if (not defined $value) {
        print "Error: value is undefined\n";
        print "metric_source: [$metric_source]\n";
        print "metric_type: [$metric_type]\n";
        return 2;
    }
    if (not $value =~ /^\d+$|^\.\d+$|^\d+\.\d*$/) {
        print "Error: $label: value [$value] is not a number\n";
        return 3;
    }
    if (not defined $timestamp_ms) {
        print "Error: timestamp is undefined\n";
        return 4;
    }
    $$metric_ref{$label}{'samples'}{int $timestamp_ms} = $value;
    return 0;
}
sub gen_cdm_metric_data {
    my $data_ref = shift;
    my $period_doc_path = shift;
    my $es_dir = shift;
    my $hostname = shift;
    my $tool = shift;
    print "data:\n";
    my $nr_samples = 0;
    my $nr_condensed_samples = 0;
    my $coder = JSON->new->ascii->canonical;
    my $json_ref = get_json_file($period_doc_path);
    my %period_doc = %$json_ref; # this is the CDM doc for the run
    open(NDJSON_DESC_FH, ">" . $es_dir . "/metrics/" . $hostname .  "/metric_desc-" . $period_doc{"period"}{"id"} . "-" . $tool . ".ndjson");
    open(NDJSON_DATA_FH, ">" . $es_dir . "/metrics/" . $hostname .  "/metric_data-" . $period_doc{"period"}{"id"} . "-" . $tool . ".ndjson");
    print "Generating CDM\n";
    for my $label (sort keys %$data_ref) {
        my $nr_label_samples = 0;
        my $nr_condensed_label_samples = 0;
        print "processing $label: ";
        if (exists $$data_ref{$label}{'samples'}) {
            my $bail = 0;
            my %series = %{$$data_ref{$label} };
            my %metric_desc = create_metric_desc_doc( \%period_doc, $series{'class'}, $series{'type'},
                                                      $tool, $series{'name_format'});
            for my $field (keys %{ $series{'names'} }) {
                $metric_desc{"metric_desc"}{'names'}{$field} = $series{'names'}{$field};
            }
            printf NDJSON_DESC_FH "%s\n", '{ "index": {} }';
            printf NDJSON_DESC_FH "%s\n", $coder->encode(\%metric_desc);
            my $begin_value;
            my $begin_timestamp;
            my $end_timestamp;
            for my $timestamp_ms (sort keys $series{'samples'}) {
                $nr_samples++;
                $nr_label_samples++;
                if (not defined $series{'samples'}{$timestamp_ms}) {
                    print "Warning: undefined value in\n";
                    print Dumper \%series;
                    $bail = 1;
                    last;
                };
                my $value = $series{'samples'}{$timestamp_ms};
                if (not defined $begin_value) { # The very first value
                    $begin_value = $value;
                    if (defined $series{'interval'}) {
                        # If we know the interval, we can calculate a $begin_timestamp
                        # and this new timestamp can be an $end_timestamp.  If we don't
                        # know the interval, we have to wait until we get another timestamp
                        $begin_timestamp = $timestamp_ms - $series{'interval'} + 1;
                    } else {
                        $begin_timestamp = $timestamp_ms + 1;
                        next;
                    }
                }
                if ($condense_samples) {
                    if ($value == $begin_value) { # Keep extending the end timestamp
                        $end_timestamp = $timestamp_ms;
                    } elsif (defined $end_timestamp) { # The value changed, so log the previous sample
                        $nr_condensed_samples++;
                        $nr_condensed_label_samples++;
                        my %metric_data = create_metric_data_doc($metric_desc{'metric_desc'}{'id'},
                            $begin_value, $begin_timestamp, $end_timestamp);
                        printf NDJSON_DATA_FH "%s\n", '{ "index": {} }';
                        printf NDJSON_DATA_FH "%s\n", $coder->encode(\%metric_data);
                        # Since we start tracking a new value, begin_value and begin/end timestamps must be reasigned
                        $begin_value = $value;
                        $begin_timestamp = $end_timestamp + 1;
                        $end_timestamp = $timestamp_ms;
                    } else { # End was not defined yet because we only had 1 sample so far
                        $end_timestamp = $timestamp_ms;
                    }
                } else {
                    $nr_condensed_samples++;
                    $nr_condensed_label_samples++;
                    my %metric_data = create_metric_data_doc($metric_desc{'metric_desc'}{'id'},
                        $begin_value, $begin_timestamp, $timestamp_ms);
                    printf NDJSON_DATA_FH "%s\n", '{ "index": {} }';
                    printf NDJSON_DATA_FH "%s\n", $coder->encode(\%metric_data);
                    $begin_value = $value;
                    $begin_timestamp = $timestamp_ms + 1;
                    
                }
            }
            if ($condense_samples and not $bail) {
                if (not defined $begin_value) { print "no beging_value\n"; print Dumper \%series; next;}
                if (not defined $begin_timestamp) { print "no begin_timestamp\n"; print Dumper \%series; next;}
                if (not defined $end_timestamp) { print "no end_timestamp\n"; print Dumper \%series; next;}
                $nr_condensed_samples++;
                $nr_condensed_label_samples++;
                # Since we only log the previous value/timestamp in the while loop, we have to log the final value/timestamp
                my %metric_data = create_metric_data_doc($metric_desc{'metric_desc'}{'id'},
                    $begin_value, $begin_timestamp, $end_timestamp);
                printf NDJSON_DATA_FH "%s\n", '{ "index": {} }';
                printf NDJSON_DATA_FH "%s\n", $coder->encode(\%metric_data);
            }
            if ($nr_label_samples > 0) {
                printf "dedup reduction: %d%%\n", 100*(1 - $nr_condensed_label_samples/$nr_label_samples);
            } else {
                print "\n";
            }
        }
    }
    close(NDJSON_DATA_FH);
    close(NDJSON_DESC_FH);
    if ($nr_samples > 0) {
        printf "dedup reduction: %d%%\n", 100*(1 - $nr_condensed_samples/$nr_samples);
    }
}

1;
