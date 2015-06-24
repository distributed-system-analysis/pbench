#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-

# Author: Andrew Theurer
#
package BenchPostprocess;

use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);

our @EXPORT_OK = qw(get_cpubusy_series calc_ratio_series calc_sum_series);

my $script = "BenchPostprocess";

sub get_cpubusy_series {
	# This will get a hash (series) with keys = timestamps and values = CPU busy
	# CPU Busy is in CPU units: 1.0 = amoutn of cpu used is equal to 1 logical CPU
	# 1.0 does not necessarily mean exactly 1 of the cpus was used at 100%.
	# This value is a sum of all cpus used, which may be several cpus used, each a fraction of their maximum
	
	my $params = shift;
	# This is the directory which contains the tool data: see ./sar/csv/cpu_all_cpu_busy.csv
	my $tool_dir = $params;
	$params = shift;
	# These hash, which will be populated with cpubusy data, needs to be used by reference in order to preserve the changes made
	my $cpu_busy_ref = $params;
	$params = shift;
	# We don't want data before this timestamp
	my $first_timestamp = $params;
	$params = shift;
	# We don't want data after this timestamp
	my $last_timestamp = $params;

	my $file = "$tool_dir/sar/csv/cpu_all_cpu_busy.csv";
	if (open(SAR_ALLCPU_CSV, "$file")) {
		my $timestamp_ms = 0;
		my @values;
		my $cpu_busy;
		my $cnt = 0;
		while (my $line = <SAR_ALLCPU_CSV>) {
			chomp $line;
			## The csv file has this format:
			# timestamp_ms,cpu_00,cpu_01,cpu_02,cpu_03
			# 1429213202000,10.92,6.9,5,6.66
			# 1429213205000,88.29,0.33,0.67,0
			if ( $line =~ /^timestamp/ ) {
				next;
			}
			@values = split(/,/,$line);
			$timestamp_ms = shift(@values);
			if (( $timestamp_ms <= $last_timestamp ) && ( $timestamp_ms >= $first_timestamp )) {
				my $value;
				$cpu_busy = 0;
				foreach $value (@values) {
					$cpu_busy += $value;
				}
				$$cpu_busy_ref{$timestamp_ms} = $cpu_busy/100;
				$cnt++;
			}
		}
		close(SAR_ALLCPU_CSV);
		if ($cnt > 0) {
			return 0;
		} else {
			printf "$script: no sar timestamps in $file fall within given range: $first_timestamp - $last_timestamp\n";
			return 1;
		}
	} else {
		printf "$script: could not find file $file\n";
		return 1;
	}
}

sub calc_ratio_series {
	# This generates a new hash (using the hash referfence, $ratio) from two existing hashes
	# (hash references $numerator and $denominator).  This is essentially:
	# %ratio_hash = %numerator_hash / %denominator_hash
	# Each hash is a time series, with a value for each timestamp key
	# The timestamp keys do not need to match exactly.  Values are interrepted linearly
	

	# These hashes need to be used by reference in order to preserve the changes made
	my $params = shift;
	my $numerator = $params;
	$params = shift;
	my $denominator = $params;
	$params = shift;
	my $ratio = $params;

	# This would be fairly trivial if the two hashes we are dealing with had the same keys (timestamps), but there
	# is no guarantee of that.  What we do is key off the timestamps of the second hash and interpolate a value from the first hash.
	my $count = 0;
	my $prev_numerator_timestamp_ms = 0;
	my @numerator_timestamps = (sort {$a<=>$b} keys %{$numerator});
	my @denominator_timestamps = (sort {$a<=>$b} keys %{$denominator});
	while ($denominator_timestamps[0] < $numerator_timestamps[0]) {
		shift(@denominator_timestamps) || last;
	}
	# remove any "trailing" timestamps: timestamps from denominator that come after the last timestamp in numerator
	while ($denominator_timestamps[-1] >= $numerator_timestamps[-1]) {
		my $unneeded_denominator_timestamp = pop(@denominator_timestamps);
		delete $$denominator{$unneeded_denominator_timestamp} || last;
	}
	my $numerator_timestamp_ms = shift(@numerator_timestamps);
	my $denominator_timestamp_ms;
	for $denominator_timestamp_ms (@denominator_timestamps) {
		# don't attempt to calculate a ratio if we have divide by zero
		if ($$denominator{$denominator_timestamp_ms} == 0) {
			next;
		}
		# find a pair of consecutive numerator timestamps which are before & after the denominator timestamp
		# these timestamps are ordered, so once the first numerator timestamp is found that is >= denominator timestamp,
		# the previous numerator timestamp should be < denominator timestamp.
		# print "looking for suitable pair of timestamps\n";
		while ($numerator_timestamp_ms <= $denominator_timestamp_ms) {
			$prev_numerator_timestamp_ms = $numerator_timestamp_ms;
			$numerator_timestamp_ms = shift(@numerator_timestamps) || last;
		}
		my $numerator_value_base = $$numerator{$prev_numerator_timestamp_ms};
		my $denominator_prev_numerator_timestamp_diff_ms = ($denominator_timestamp_ms - $prev_numerator_timestamp_ms);
		my $value_adj = 0;
		if ($denominator_prev_numerator_timestamp_diff_ms != 0) {
			my $numerator_prev_numerator_timestamp_diff_ms = ($numerator_timestamp_ms - $prev_numerator_timestamp_ms);
			my $value_diff = $$numerator{$numerator_timestamp_ms} - $numerator_value_base;
			$value_adj = $value_diff * $denominator_prev_numerator_timestamp_diff_ms/$numerator_prev_numerator_timestamp_diff_ms;
		}
		my $numerator_value_interp = $numerator_value_base + $value_adj;
		$$ratio{$denominator_timestamp_ms} = $numerator_value_interp/$$denominator{$denominator_timestamp_ms};
		# print "$$ratio{$denominator_timestamp_ms} :  $numerator_value_interp / $$denominator{$denominator_timestamp_ms}\n";
		$count++;
	}
}

sub calc_sum_series {
	# This takes the sum of two hashes (hash references $add_from_ref and $add_to_ref)
	# and stores the values in $add_to_hash.  This is essentially:
	# %add_to_hash = %add_from_hash + %add_to_hash
	# Each hash is a time series, with a value for each timestamp key
	# The timestamp keys do not need to match exactly.  Values are interrepted linearly
	
	# These hashes need to be used by reference in order to preserve the changes made
	my $params = shift;
	my $add_from_ref = $params;
	$params = shift;
	my $add_to_ref = $params;
	# This would be fairly trivial if the two hashes we are dealing with had the same keys (timestamps), but there
	# is no guarantee of that.  What we have to do is key off the timestamps of the second hash (where we store the sum)
	# and interpolate a value from the first hash.
	my $count = 0;
	my $prev_stat1_timestamp_ms = 0;
	my @stat1_timestamps = (sort {$a<=>$b} keys %{$add_from_ref});
	# print "stat1_timestamps: @stat1_timestamps\n";
	my @stat2_timestamps = (sort {$a<=>$b} keys %{$add_to_ref});
	# print "stat2_timestamps: @stat2_timestamps\n";
	# remove any "leading" timestamps: timestamps from stat2 that come before first timestamp in stat1
	# print "removing leading samples\n";
	while ($stat2_timestamps[0] < $stat1_timestamps[0]) {
		# print "stat2:$stat2_timestamps[0] < stat1:$stat1_timestamps[0]\n";
		my $unneeded_stat2_timestamp = shift(@stat2_timestamps);
		delete $$add_to_ref{$unneeded_stat2_timestamp} || last;
	}
	# remove any "trailing" timestamps: timestamps from stat2 that come after the last timestamp in stat1
	# print "removing trailing samples\n";
	while ($stat2_timestamps[-1] >= $stat1_timestamps[-1]) {
		my $unneeded_stat2_timestamp = pop(@stat2_timestamps);
		#printf "deleting this timestamp from stat2: $unneeded_stat2_timestamp value: $$add_to_ref{$unneeded_stat2_timestamp}\n";
		delete $$add_to_ref{$unneeded_stat2_timestamp} || last;
	}
	my $stat1_timestamp_ms = shift(@stat1_timestamps);
	my $stat2_timestamp_ms;
	for $stat2_timestamp_ms (@stat2_timestamps) {
		# find a pair of consecutive stat1 timestamps which are before & after the stat2 timestamp
		# these timestamps are ordered, so once the first stat1 timestamp is found that is >= stat2 timestamp,
		# the previous stat1 timestamp should be < stat2 timestamp.
		# print "looking for suitable pair of timestamps\n";
		while ($stat1_timestamp_ms <= $stat2_timestamp_ms) {
			# print "looking for a stat1_timestamp_ms:$stat1_timestamp_ms that is > $stat2_timestamp_ms\n";
			$prev_stat1_timestamp_ms = $stat1_timestamp_ms;
			$stat1_timestamp_ms = shift(@stat1_timestamps) || return;
		}
		# print "[$prev_stat1_timestamp_ms] - [$stat1_timestamp_ms]\n";
		my $stat1_value_base = $$add_from_ref{$prev_stat1_timestamp_ms};
		# if the stat2 timestamp is different from the first $stat1 timestamp, then adjust the value based on the difference of time and values
		my $stat2_prev_stat1_timestamp_diff_ms = ($stat2_timestamp_ms - $prev_stat1_timestamp_ms);
		my $value_adj = 0;
		if ($stat2_prev_stat1_timestamp_diff_ms != 0) {
			my $stat1_prev_stat1_timestamp_diff_ms = ($stat1_timestamp_ms - $prev_stat1_timestamp_ms);
			my $value_diff = $$add_from_ref{$stat1_timestamp_ms} - $stat1_value_base;
			$value_adj = $value_diff * $stat2_prev_stat1_timestamp_diff_ms/$stat1_prev_stat1_timestamp_diff_ms;
		}
		my $stat1_value_interp = $stat1_value_base + $value_adj;
		# if ($count == 0) {print "add_from: $stat1_value_interp  add_to(current): $$add_to_ref{$stat2_timestamp_ms}  ";}
		$$add_to_ref{$stat2_timestamp_ms} = $$add_to_ref{$stat2_timestamp_ms} + $stat1_value_interp;
		# printf " timestamp: $stat2_timestamp_ms  value: $$add_to_ref{$stat2_timestamp_ms}\n";
		# if ($count  == 0) { print "add_to(new): $$add_to_ref{$stat2_timestamp_ms} ]\n";}
		$count++;
	}
}

1;
