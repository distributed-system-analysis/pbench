#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 4 -*-
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=perl
# Author: Andrew Theurer

package PbenchBase;
use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use JSON;

our @EXPORT_OK = qw(get_json_file put_json_file get_benchmark_names get_clients get_pbench_run_dir
                    get_pbench_install_dir get_pbench_config_dir get_pbench_bench_config_dir
                    get_benchmark_results_dir get_params remove_params remove_element get_hostname
                    get_pbench_datetime load_benchmark_config begin_run end_run interrupt_run
                    metadata_log_record_iteration);

my $script = "PbenchBase.pm";

sub get_hostname {
    my $hostname = `hostname -s`;
    chomp $hostname;
    return $hostname;
}

sub get_pbench_run_dir {
    my $dir = $ENV{'pbench_run'};
    if (not defined $dir) {
        $dir = `pbench-config pbench_run pbench-agent 2>/dev/null`;
    } elsif (not defined $dir) {
        $dir = "/var/lib/pbench-agent";
    }
    chomp $dir;
    return $dir;
}

sub get_pbench_install_dir {
    my $dir = $ENV{'pbench_install_dir'}; # typically /opt/pbench-agent
    chomp $dir;
    return $dir;
}

sub get_pbench_config_dir {
    return get_pbench_install_dir() . "/config";
}

sub get_pbench_bench_config_dir {
    return get_pbench_install_dir() . "/config/benchmark";
}

# Process @ARGV-like array and return a hash with key=argument and value=value
sub get_params {
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
        # Copy the argv so we can iterate over all elements even if some are removed
        my @argv = @$argv_ref;
        for my $param (@argv) {
            chomp $param;
            if ($param =~ /--(\S+)=(\S+)/) {
                if ($1 eq $arg) {
                    splice(@{ $argv_ref }, $index, 1);
                    $index--;
                }
            }
            $index++;
        }
    }
}

# Read a json file and put in hash the return value is a reference
sub get_json_file {
    my $filename = shift;
    my $coder = JSON->new;
    open(JSON_FH, $filename) || die("$script: could not open file $filename\n");
    my $json_text = "";
    while ( <JSON_FH> ) {
        $json_text .= $_;
    }
    close JSON_FH;
    my $perl_scalar  = $coder->decode($json_text);
    return $perl_scalar;
}

sub put_json_file {
    my $doc_ref = shift;
    my $filename = shift;
    my $coder = JSON->new->ascii->canonical;
    my $json_text  = $coder->encode($doc_ref);
    open(JSON_FH, ">" . $filename) || die "$script: could not open file $filename: $!\n";
    printf JSON_FH "%s", $json_text;
    close(JSON_FH);
}

# Find all the benchmarks in the pbench configuraton data
sub get_benchmark_names {
    my $dir = shift;
    my @benchmarks;
    opendir(my $dh, $dir) || die("Could not open directory $dir: $!\n");
    my @entries = readdir($dh);
    for my $entry (grep(!/pbench/, @entries)) {
        if ($entry =~ /^(\w+)\.json$/) {
            push(@benchmarks, $1);
        }
    }
    return @benchmarks;
}

# Scan the cmdline and return an array of client hostnames in --clients= if present
sub get_clients {
    my @clients;
    for my $param (@_) {
        if ($param =~ /\-\-clients\=(.+)/) {
            @clients = split(/,/, $1);
        }
    }
    return @clients;
}

sub get_pbench_datetime { #our common date & time format
    my $datetime = $ENV{'date'};
    if (defined $datetime) {
        $datetime = `date --date $datetime --utc +"%Y.%m.%dT%H.%M.%S"`;
    } else {
        $datetime = `date --utc +"%Y.%m.%dT%H.%M.%S"`;
    }
    chomp $datetime;
    return $datetime;
}

# Get a new benchmark directory -needed if you are going to run a benchmark
sub get_benchmark_results_dir {
    my $benchmark = shift;
    my $config = shift;
    my $datetime = shift;
    my $basedir = get_pbench_run_dir();
    my $benchdir = $basedir . "/" . $benchmark . "_" . $config . "_" . $datetime;
}

# Load a benchmark json file which tells us how to run a benchmark
sub load_benchmark_config {
    my $pbench_bench_config_dir = shift;
    my $benchmark_name = shift;
    my $benchmark_spec_file = $pbench_bench_config_dir . "/" .  $benchmark_name . ".json";
    my $json_ref = get_json_file($benchmark_spec_file);
    return %$json_ref
}

sub begin_run {
    my $benchmark_run_dir = shift;
    my $benchmark = shift;
    my $config = shift;
    my $date = shift;
    my $sysinfo = shift;
    my $tool_group = shift;

    system("benchmark_run_dir='" . $benchmark_run_dir . "' benchmark='" . $benchmark . "' config='" . $config . "' date='" . $date . "' pbench-tool-meister-start --sysinfo='" . $sysinfo . "' " . $tool_group);
}

sub end_run {
    my $tool_group = shift;
    my $sysinfo = shift;

    # Stop tool meister normally.
    system("pbench-tool-meister-stop --sysinfo='" . $sysinfo . "' " . $tool_group);
}

sub interrupt_run {
    my $tool_group = shift;

    # Stop tool meister indicating it is being interrupted.
    system("pbench-tool-meister-stop --sysinfo=none --interrupt " . $tool_group);
}

sub metadata_log_record_iteration {
    my $benchmark_run_dir = shift;
    my $iteration_id = shift;
    my $iteration_params = shift;
    my $iteration_name = shift;

    my $mdlog = $benchmark_run_dir . "/metadata.log";
    system("echo " . $iteration_id    . " | pbench-add-metalog-option " . $mdlog . " iterations/" . $iteration_name . " iteration_number");
    system("echo " . $iteration_name  . " | pbench-add-metalog-option " . $mdlog . " iterations/" . $iteration_name . " iteration_name");
    my @params = split(/\s+/, $iteration_params);
    while (scalar @params > 0) {
        my $param = shift @params;
        if ($param =~ /\-\-(\S+)\=(\S+)/) {
            system("echo " . $2 . " | pbench-add-metalog-option " . $mdlog . " iterations/" . $iteration_name . " " . $1);
        }
    }

    return($iteration_name);
}
1;
