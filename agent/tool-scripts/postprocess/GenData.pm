#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-

# Author: Andrew Theurer
#
package GenData;

use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);

our @EXPORT_OK = qw(gen_data);

sub gen_data {
	my $script = basename($0);

	my $params = shift;
	my %stats = %$params;

	$params = shift;
	my %graph_types = %$params;

	$params = shift;
	my %thresholds = %$params;

	my $dir = shift;
	my $skipcsvtypecheck = shift;
	if (not defined($skipcsvtypecheck)) {
		$skipcsvtypecheck = 0;
	}

	# define the graph types
	# if you want something other than lineChart, put it here
	# my %graph_type;
	# threshold for displying a series in a graph
	my $htmlpage;
	my $chart;
	my %maxval;
	my %counts;
	my $filename;
	my $timestamp_ms;
	
	# Generate the CSV file, and don't filter out anything based on a
	# threshold, and generate the averages for each series.
	my $csv;
	$csv = $dir . "/csv";
	unless(-d $csv or mkdir $csv) { die "$script: could not create $csv directory\n"; }

	for $htmlpage (sort keys %stats) {
		#printf "htmlpage = $htmlpage\n";

		my %totals;

		# compute the average value for each stat while emitting
		# .csv data

		for $chart (sort keys %{$stats{$htmlpage}}) {
			#printf "\tchart = $chart\n";

			$filename = $csv . "/" . $htmlpage. "_" .$chart . ".csv";
			open(TOOL_CSV, ">$filename") || die "$script: could not open $filename\n";

			# first check whether the timestamps in the different series agree: if so,
			# we'll generate a normal (type-1) csv file:  each row will have the form
			#   ts, m0, m1, m2, ..., mN
			#
			# if not, we'll generate a type-2 csv file: each row will consist of pairs
			# of (ts, mX) values for each metric. We have to make sure that the rows
			# are padded appropriately to the length of the longest time series. If the
			# time series is shorter, we'll add empty cells.
			my $series_key;
			my @series_keys;
			@series_keys = sort keys %{$stats{$htmlpage}{$chart}};

			my $csvtype=1;
			# the following check is expensive, so we only do it conditionally
			# Currently, the only user is uperf-postprocess.
			if ($skipcsvtypecheck == 1) {
				my $sk;
				for $sk (@series_keys) {
					#printf "\t\tsk = $sk\n";
					for $series_key (@series_keys) {
						if ($sk ne $series_key) {
							#printf "\t\t\tseries_key = $series_key\n";
							# TODO: we need only loop over the series keys *after* sk in the list.
							for $timestamp_ms (sort {$a <=> $b} (keys %{$stats{$htmlpage}{$chart}{$sk}})) {
								#printf "\t\t\t\ttimestamp_ms = $timestamp_ms\n";
								if ( not defined $stats{$htmlpage}{$chart}{$series_key}{$timestamp_ms} ) {
									#printf "\t\t\t\t\t $timestamp_ms missing\n";
									$csvtype=2;
									last;
								}
							}
						}
					}
				}
				#printf "csvtype is $csvtype for $filename\n";
				# in the second pass, we produce lines of the form
				#     ts1,m1,ts2,m2,...,tsN,mN
				# if we run out of entries in a particular series, pad the entry with empty values:
				#     ts1,m1,,,ts3,m3...,tsN,mN
			}

			if ($csvtype == 2) {
				# Emit header row for .csv file
				printf TOOL_CSV "timestamp_%s_ms,%s", $series_keys[0], $series_keys[0];
				for $series_key (@series_keys[1 .. $#series_keys]) {
					printf TOOL_CSV ",timestamp_%s_ms,%s", $series_key, $series_key;
				}
				printf TOOL_CSV "\n";

				for $series_key (@series_keys) {
					$maxval{$htmlpage}{$chart}{$series_key} = -999999999;
				}

				my %ts;
				my $sk;
				for $sk (@series_keys) {
					@{$ts{$sk}} = sort {$a <=> $b} (keys %{$stats{$htmlpage}{$chart}{$sk}});
					$counts{$chart}{$sk} = 0;
				}
				my $maxlength = max(map scalar(keys( %{ $stats{$htmlpage}{$chart}{$_} } )), @series_keys);
				# print "maxlength=$maxlength\n";

				for (my $i=0; $i < $maxlength; $i++) {
					# for each series, get the timestamp and the metric - if undefined, make them blank.
					my $value;
					for $series_key (@series_keys) {
						if (defined $ts{$series_key}[$i]) {
							$timestamp_ms = $ts{$series_key}[$i];
							$counts{$chart}{$series_key} += 1;
							if ( not defined $stats{$htmlpage}{$chart}{$series_key}{$timestamp_ms} ) {
								die "$script: timestamp $timestamp_ms missing for ($htmlpage, $chart, $series_key)";
							}
							$value = $stats{$htmlpage}{$chart}{$series_key}{$timestamp_ms}; 
							$totals{$chart}{$series_key} += $value;
							if ($value > $maxval{$htmlpage}{$chart}{$series_key}) {
								$maxval{$htmlpage}{$chart}{$series_key} = $value;
							}
						} else {
							$timestamp_ms="";
							$value="";
						}
						# assumption: series keys are unique
						if ($series_key ne $series_keys[0]) {
							print TOOL_CSV ",";
						}
						printf TOOL_CSV "$timestamp_ms,$value";
					}
					printf TOOL_CSV "\n";
				}
			} else {
				# Emit header row for .csv file
				printf TOOL_CSV "timestamp_ms";
				for $series_key (@series_keys) {
					printf TOOL_CSV ",$series_key";
				}
				printf TOOL_CSV "\n";

				my %ts;
				for $series_key (@series_keys) {
					$maxval{$htmlpage}{$chart}{$series_key} = -999999999;
					for $timestamp_ms (sort {$a <=> $b} (keys %{$stats{$htmlpage}{$chart}{$series_key}})) {
						$ts{$timestamp_ms} = 1;
					}
				}

				my $i = 0;
				for $timestamp_ms (sort {$a <=> $b} (keys %ts)) {
					my $value;
					print TOOL_CSV "$timestamp_ms";
					for $series_key (@series_keys) {
						# this should not happen any more, but paranoid checking doesn't hurt.
						if ( defined $stats{$htmlpage}{$chart}{$series_key}{$timestamp_ms} ) {
							$value = $stats{$htmlpage}{$chart}{$series_key}{$timestamp_ms}; 
							$totals{$chart}{$series_key} += $value;
							if ($value > $maxval{$htmlpage}{$chart}{$series_key}) {
								$maxval{$htmlpage}{$chart}{$series_key} = $value;
							}
						} else {
							$value = "";
						}
						printf TOOL_CSV ",$value";
					}
					printf TOOL_CSV "\n";
					$i += 1;
				}
				for $series_key (@series_keys) {
					$counts{$chart}{$series_key} = $i;
				}
			}
			close(TOOL_CSV);
		}

		$filename = $dir . "/" . $htmlpage . "-average.txt";
		open(TOOL_AVG, ">$filename") || die "$script: could not open $filename\n";
		for $chart (sort keys %totals) {
			my $series_key;
			for $series_key (sort keys %{$totals{$chart}}) {
				my $count;
				my $total;
				$count = $counts{$chart}{$series_key};
				$total = $totals{$chart}{$series_key};
				printf TOOL_AVG "$chart-$series_key=%f\n", $total / $count;
			}
		}
		close(TOOL_AVG);
	}

	# generate the html files
	for $htmlpage (sort keys %stats) {
		$filename = $dir . "/" . $htmlpage . ".html";
		open(TOOL_HTML, ">$filename") || die "$script: could not open $filename\n";
		# Write the html header
		printf TOOL_HTML "<!DOCTYPE HTML>\n";
		printf TOOL_HTML "<html>\n";
		printf TOOL_HTML "  <head>\n";
		printf TOOL_HTML "    <meta charset=\"utf-8\">\n";
		printf TOOL_HTML "    <link href=\"/static/css/v0.2/nv.d3.css\" rel=\"stylesheet\" type=\"text/css\" media=\"all\">\n";
		printf TOOL_HTML "    <link href=\"/static/css/v0.2/pbench_utils.css\" rel=\"stylesheet\" type=\"text/css\" media=\"all\">\n";
		printf TOOL_HTML "    <script src=\"/static/js/v0.2/function-bind.js\"></script>\n";
		printf TOOL_HTML "    <script src=\"/static/js/v0.2/fastdom.js\"></script>\n";
		printf TOOL_HTML "    <script src=\"/static/js/v0.2/d3.js\"></script>\n";
		printf TOOL_HTML "    <script src=\"/static/js/v0.2/nv.d3.js\"></script>\n";
		printf TOOL_HTML "    <script src=\"/static/js/v0.2/saveSvgAsPng.js\"></script>\n";
		printf TOOL_HTML "    <script src=\"/static/js/v0.2/pbench_utils.js\"></script>\n";
		printf TOOL_HTML "  </head>\n";
		printf TOOL_HTML "  <body class=\"with-3d-shadow with-transitions\">\n";
		printf TOOL_HTML "    <h2 class=\"page-header\">%s - %s</h2>\n", basename($dir), "$htmlpage";

		my $chartnum=1;
		for $chart (sort keys %{$stats{$htmlpage}}) {
			my $series;
			my $series_num = 0;
			for $series (sort keys %{$stats{$htmlpage}{$chart}}) {
				# if there is a threshold declared and this series does not meet that, then do not graph it
				if (( defined $thresholds{$htmlpage}{$chart} ) && ( $maxval{$htmlpage}{$chart}{$series} <= $thresholds{$htmlpage}{$chart} )) {
					next;
				}
				$series_num++;
			}
			if ( $series_num > 0 ) { # if there is at least one series then create the graph
				my $this_graph_type = "lineChart";
				if (defined $graph_types{$htmlpage}{$chart} ) {
					$this_graph_type = $graph_types{$htmlpage}{$chart};
				}
				printf TOOL_HTML "    <div class=\"chart\">\n";
				printf TOOL_HTML "      <h3 class=\"chart-header\">%s\n", "$chart";
				printf TOOL_HTML "        <button id=\"save%d\">Save as Image</button>\n", $chartnum;
				printf TOOL_HTML "        <div id=\"svgdataurl%d\"></div>\n", $chartnum;
				printf TOOL_HTML "      </h3>\n";
				printf TOOL_HTML "      <svg id=\"chart%d\"></svg>\n", $chartnum;
				printf TOOL_HTML "      <canvas id=\"canvas%d\" style=\"display:none\"></canvas>\n", $chartnum;
				printf TOOL_HTML "      <script>\n";
				if ( defined $thresholds{$htmlpage}{$chart} ) {
					printf TOOL_HTML "        constructChart(\"%s\", %d, \"%s\", %.2f);\n", $this_graph_type, $chartnum, $htmlpage . '_' . $chart, $thresholds{$htmlpage}{$chart};
				} else {
					printf TOOL_HTML "        constructChart(\"%s\", %d, \"%s\");\n", $this_graph_type, $chartnum, $htmlpage . '_' . $chart;
				}
				printf TOOL_HTML "      </script>\n";
				printf TOOL_HTML "    </div>\n";
				$chartnum++;
			}
		}
		if ( $chartnum == 1 ) {
			for $chart (sort keys %{$stats{$htmlpage}}) {
				my $series;
				my $series_num = 0;
				my $series_tot = 0;
				for $series (sort keys %{$stats{$htmlpage}{$chart}}) {
					$series_tot++;
					# if there is a threshold declared and this series does not meet that, then do not graph it
					if (( defined $thresholds{$htmlpage}{$chart} ) && ( $maxval{$htmlpage}{$chart}{$series} <= $thresholds{$htmlpage}{$chart} )) {
						next;
					}
					$series_num++;
				}
				if ( $series_num == 0 ) {
					printf TOOL_HTML "    <h3 class=\"chart-header\">%s</h3>\n", "$chart";
					if ( $series_tot == 0 ) {
						printf TOOL_HTML "    <p class=\"chart-reason\">No data to graph.</p>\n";
					} else {
						if ( $series_tot > $series_num ) {
							printf TOOL_HTML "    <p class=\"chart-reason\">No data from any series met set thresholds for graphing.</p>\n";
						} else {
							die "Logic bomb!\n";
						}
					}
					printf TOOL_HTML "    <br>\n";
				}
			}
		}
		printf TOOL_HTML "  </body>\n</html>\n";
		close(TOOL_HTML);
	}
}

1;
