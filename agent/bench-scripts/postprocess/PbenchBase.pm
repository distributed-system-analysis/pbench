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

our @EXPORT_OK = qw(get_json get_benchmark_names);
my $script = "PbenchBase.pm";
my $sub;

# read a json file and put in hash
# the return value is a reference
sub get_json {
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

sub get_benchmark_names {
	$sub = "get_benchmark_names()";
	my $dir = shift;
	opendir(my $dh, $dir) || die("$script $sub: Could not open directory $dir: $!\n");
	my @entries = readdir($dh);
	for my $entry (grep(!/pbench/, @entries)) {
		if ($entry =~ /^(\w+)\.json$/) {
			printf "%s\n", $1;
		}
	}
}

1;
