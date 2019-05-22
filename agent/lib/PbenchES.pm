#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 4 -*-
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=perl
# Author: Andrew Theurer

package PbenchES;
use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use Time::HiRes qw(gettimeofday);
use REST::Client;
use JSON;
use Data::Dumper;
use Data::UUID;
use SigFigs;
use Array::Diff qw(:all);
use PbenchCDM qw(get_cdm_ver get_cdm_rel);

our @EXPORT_OK = qw(get_primary_metric
                    get_sample_ids
                    es_get_query
                    get_primary_period_id
                    get_name_format_field_names
                    get_name_format
                    get_metric_label
                    get_metric_ids_from_term
                    get_metric_ids
                    get_common_time_domain
                    get_weighted_avg_agg
                    get_many_metric_results_from_ids
                    get_many_metric_results_from_term
                    get_metric_data
                    get_aggregation_from_name_format
                    gen_metric_group_terms
                    gen_metric_source_types
                    gen_label_to_terms
                    list_all_metrics
                    get_bench_name
                    get_primary_period_name);

my %req_header = ("Content-Type" => "application/json");
my $coder = JSON::MaybeXS->new->ascii->canonical;
my $template =
'{
  "size": 100,
  "query" : {
      "bool": {
        "filter": [
        ]
      }
    }
}';

sub debug_log {
    if (exists $ENV{'ES_DEBUG'} and $ENV{'ES_DEBUG'} > 0) {
        my @time = gettimeofday;
        printf "[%s]%s\n", join(".", @time), shift;
    }
}

sub get_index_basename {
    return "cdmv" . get_cdm_ver . get_cdm_rel . "-";
}


sub es_get_query {
    my $host = shift;
    my $req = get_index_basename . shift;
    my $body = shift;
    my $desc = shift;
    my $client = REST::Client->new();
    $client->setHost($host);
    my %req_header = ("Content-Type" => "application/json");
    debug_log(sprintf "%s:\nRequest: http://%s/%s\nbody: %s\n\n", $desc, $host, $req, $body);
    $client->request('GET', $req, $body, \%req_header);
    my $response = $client->responseContent();
    debug_log($response);
    return $response;
}

sub get_primary_metric {
    my $host = shift;
    my $iter_id = shift;
    my $iter_req_ref = $coder->decode($template);
    push @{ $$iter_req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"iteration.id": "' . $iter_id . '"}}');
    my $iter_req_json = $coder->encode($iter_req_ref);
    my $resp = es_get_query($host, "iteration/iteration/_search", $iter_req_json, "Query to get iteration document");
    my $iter_resp_ref = $coder->decode($resp);
    #$bench_name = $$iter_resp_ref{'hits'}{'hits'}[0]{'_source'}{'run'}{'bench'}{'name'};
    #printf "bench_name:\n%s\n\n", $bench_name;
    #printf "iteration.params:\n%s\n\n", $$iter_resp_ref{'hits'}{'hits'}[0]{'_source'}{'iteration'}{'params'};
    # get to get all sample docs for an iteration
    my $samp_req_ref = $coder->decode($iter_req_json);
    $$samp_req_ref{"aggs"}{"source"}{"terms"}{"field"} = "iteration.primary_metric";
    my $samp_req_json = $coder->encode($samp_req_ref);
    my $samp_resp = es_get_query($host, "sample/sample/_search", $samp_req_json, "Query to get iteration.primary_metric from sample documents");
    my $samp_resp_ref = $coder->decode($samp_resp);
    my $primary_metric;
    if (exists $$samp_resp_ref{"aggregations"}{"source"}{"buckets"} and scalar @{ $$samp_resp_ref{"aggregations"}{"source"}{"buckets"} } == 1) {
        $primary_metric = $$samp_resp_ref{"aggregations"}{"source"}{"buckets"}[0]{"key"};
        return $primary_metric;
    } else {
        die "ERROR: Could not find just one primary for this iteration";
    }
}

sub get_primary_period_name {
    my $host = shift;
    my $sample_id = shift;
    my $req_ref = $coder->decode($template);
    push @{ $$req_ref{"query"}{"bool"}{"filter"} },
    $coder->decode('{"term": {"sample.id": "' . $sample_id . '"}}');
    my $req_json = $coder->encode($req_ref);
    my $resp = es_get_query($host, "sample/sample/_search", $req_json, "Query to get iteration.primary_period sample documents");
    my $resp_ref = $coder->decode($resp);
    return $$resp_ref{'hits'}{'hits'}[0]{'_source'}{'iteration'}{'primary_period'};
}

sub get_sample_ids {
    my $host = shift;
    my $iter_id = shift;
    my $req_ref = $coder->decode($template);
    push @{ $$req_ref{"query"}{"bool"}{"filter"} },
    $coder->decode('{"term": {"iteration.id": "' . $iter_id . '"}}');
    my $req_json = $coder->encode($req_ref);
    my $resp = es_get_query($host, "sample/sample/_search", $req_json, "Query to get sample documents");
    my $resp_ref = $coder->decode($resp);
    #return $$iter_resp_ref{'hits'}{'hits'}[0]{'_source'}{'run'}{'bench'}{'name'};
    my @sample_ids;
    foreach my $samp ( @{ $$resp_ref{'hits'}{'hits'} } ) {
        push @sample_ids, $$samp{'_source'}{'sample'}{'id'};
    }
    return @sample_ids;
}

sub get_bench_name {
    my $host = shift;
    my $iter_id = shift;
    my $iter_req_ref = $coder->decode($template);
    push @{ $$iter_req_ref{"query"}{"bool"}{"filter"} },
     $coder->decode('{"term": {"iteration.id": "' . $iter_id . '"}}');
     my $iter_req_json = $coder->encode($iter_req_ref);
     my $resp = es_get_query($host, "iteration/iteration/_search", $iter_req_json, "Query to get iteration document");
     my $iter_resp_ref = $coder->decode($resp);
     return $$iter_resp_ref{'hits'}{'hits'}[0]{'_source'}{'run'}{'bench'}{'name'};
}

sub get_primary_period_id {
    my $host = shift;
    my $sample_id = shift;
    my $primary_period = shift;
    my $req_ref = $coder->decode($template);
    push @{ $$req_ref{"query"}{"bool"}{"filter"} },
         $coder->decode('{"term": {"period.name": "' . $primary_period . '"}}');
    push @{ $$req_ref{"query"}{"bool"}{"filter"} },
         $coder->decode('{"term": {"sample.id": "' . $sample_id . '"}}');
    my $req_json = $coder->encode($req_ref);
    my $resp = es_get_query($host, "period/period/_search", $req_json, "Query for primary period");
    my $peri_ref = $coder->decode($resp);
    if (scalar @{ $$peri_ref{'hits'}{'hits'} } == 1 ) { # Found exactly 1 primary period, which is what we want
        my %peri = %{ $$peri_ref{'hits'}{'hits'}[0] };
        my $period_id = $peri{'_source'}{'period'}{'id'};
        return $period_id;
    }
}
# Call with the name_format string, like "%host%-%socket%" and return an array of field names, like ('host', 'socket');
sub get_name_format_field_names {
    my $name_format = shift;
    my @field_names;
    while ( $name_format =~ /\%\S+\%/ ) {
        $name_format =~ s/([^\%]*)\%(\w+)\%(\.*)/$3/;
        push @field_names, $2;
    }
    return @field_names;
}

sub get_name_format {
    my $host = shift;
    my $period_id = shift;
    my $metric_source = shift;
    my $metric_type = shift;

    my $metr_req_ref = $coder->decode($template);
    push @{ $$metr_req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"period.id": "' . $period_id . '"}}');
    push @{ $$metr_req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"metric_desc.source": "' . $metric_source . '"}}');
    push @{ $$metr_req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"metric_desc.type": "' . $metric_type . '"}}');
    $$metr_req_ref{"aggs"}{"source"}{"terms"}{"field"} = "metric_desc.name_format";
    $$metr_req_ref{"size"} = 0;
    my $metr_req_json = $coder->encode($metr_req_ref);
    my $metr_resp = es_get_query($host, "metric_desc/metric_desc/_search", $metr_req_json, "Query to get name_format");
    my $metr_resp_ref = $coder->decode($metr_resp);
    if (scalar @{ $$metr_resp_ref{"aggregations"}{"source"}{"buckets"} } == 1) {
        my $name_format = $$metr_resp_ref{"aggregations"}{"source"}{"buckets"}[0]{"key"};
        return $name_format;
    }
}

sub get_metric_ids_from_term {
    my $host = shift;
    my $period_id = shift;
    my $terms = shift;
    my %metric_ids_by_terms;
    # the next request will start with our base reqeust from the metric request,
    # where run/iteration/sample/period/metric.source/metric.type
    my $req_ref = $coder->decode($template);
    push @{ $$req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"period.id": "' . $period_id . '"}}');
    my $terms_ref = $coder->decode('[' . $terms . ']');
    # add to, not replace, the existing terms in the filter
    my @filter = (@{ $$req_ref{"query"}{"bool"}{"filter"} }, @{ $terms_ref});
    $$req_ref{"query"}{"bool"}{"filter"} = \@filter;
    $$req_ref{"size"} = 10000; # let's hope we get nowhere even close to this number, but we'll
                              # check if we do below
    #$$req_ref{"aggs"}{"source"}{"terms"}{"field"} = "metric_desc.id";
    my $req_json = $coder->encode($req_ref);
    my $resp = es_get_query($host, "metric_desc/metric_desc/_search", $req_json, "Query to get the mertic id from " . $terms);
    my $resp_ref = $coder->decode($resp);
    my $found_docs = 0;
    #print Dumper 
    my $num_expected_docs = $$resp_ref{'hits'}{'total'};
    if ($num_expected_docs > $$req_ref{"size"}) {
        die "The number of documents requested ($num_expected_docs) exceeds the 'size' parameter ($$req_ref{'size'}) set in this query\n";
    }
    my @metric_ids;
    for my $hit (@{ $$resp_ref{'hits'}{'hits'} }) {
        push @metric_ids, $$hit{'_source'}{'metric_desc'}{'id'};
        $found_docs++;
    }
    if ($found_docs > 0) {
        return @metric_ids;
    } else {
        print "Failed to find any metric ids for $terms\n";
        print Dumper $resp_ref;
    }
}

# Get *all* metric IDs for a given metric_source and metric_type.
# This is useful if you want to get a single value or data-series
# for any and all metric data-series which match the metric_source
# and metric_value.  This is useful for computing a benchmark's 
# primary metric value.  It is not useful for breaking that value
# out, incrementally, into sub-components, unless you want it fully
# broken out into every single data-series.  For example, you could
# use this info to calculate the single, primary metric for a fio
# execution, or you could use it to get the data-series for every
# single fio host/job/io-type, but not that useful if you wanted
# to break it out only by every host (but not job and io-type).
# For that, you need to use gen_metric_group_terms()
sub get_metric_ids {
    my $host = shift;
    my $period_id = shift; # Required
    my $metric_source = shift; # Optional
    my $metric_type = shift; # Can only be used if $metric_source is used
    my @metric_ids;
    if (not defined $period_id) {
        return;
    }
    my $req_ref = $coder->decode($template);
    push @{ $$req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"period.id": "' . $period_id . '"}}');
    if (defined $metric_source) {
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"term": {"metric_desc.source": "' . $metric_source . '"}}');
    }
    if (defined $metric_type) {
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"term": {"metric_desc.type": "' . $metric_type . '"}}');
    }
    $$req_ref{"aggs"}{"source"}{"terms"}{"field"} = "metric_desc.id";
    my $req_json = $coder->encode($req_ref);
    my $resp = es_get_query($host, "metric_desc/metric_desc/_search", $req_json,
                "Query to get all the metric data-series for the primary metric  (fio: one data-series per host/job/IOtype)");
    my $resp_ref = $coder->decode($resp);
    for my $bucket (@{ $$resp_ref{"aggregations"}{"source"}{"buckets"} }) {
        push @metric_ids, $$bucket{"key"};
    }
    return @metric_ids;
}

sub get_common_time_domain {
    my $host = shift;
    my $period = shift;
    my @metric_ids = @_;
    my $latest_begin;
    my $earliest_end;
    # finding the time domain; the period of time where all the metrics ocurred
    foreach my $metric_id (@metric_ids) {
        my $metr_grp_req_ref = $coder->decode($template);
        $$metr_grp_req_ref{'size'} = 0;
        push @{ $$metr_grp_req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"term": {"metric_data.id": "' . $metric_id . '"}}');
            #$coder->decode('{"term": {"metric_data.id": "' . $metric_ids_by_terms{$terms} . '"}}');
        $$metr_grp_req_ref{"aggs"}{"earliest_begin"}{"min"}{"field"} = "metric_data.begin";
        $$metr_grp_req_ref{"aggs"}{"latest_end"}{"max"}{"field"} = "metric_data.end";
        my $metr_grp_req_json = $coder->encode($metr_grp_req_ref);
        my $metr_grp_resp = es_get_query($host, "metric_data/metric_data/_search",
                                        $metr_grp_req_json, "Query to find time domain for " .
                                        join(" ", @metric_ids));
        my $metr_grp_resp_ref = $coder->decode($metr_grp_resp);
        my $earliest_begin = $$metr_grp_resp_ref{"aggregations"}{"earliest_begin"}{"value"};
        if (not defined $latest_begin or $earliest_begin > $latest_begin) {
            $latest_begin = $earliest_begin;
        }
        my $latest_end = $$metr_grp_resp_ref{"aggregations"}{"latest_end"}{"value"};
        if (not defined $earliest_end or $latest_end < $earliest_end) {
            $earliest_end = $latest_end;
        }
    }
    return ($latest_begin, $earliest_end);
}

sub get_weighted_avg_agg {
    my $req_ref = shift;
    my $begin = shift;
    my $end = shift;
    my $mode = shift;

    if ($mode eq 'scripted-expression') {
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"value"}{"field"} = "metric_data.value";
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"lang"} = "expression";
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"params"}{"end"} = int $end;
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"params"}{"begin"} = int $begin;
        # The script must check to see if the metric.begin is earlier than the time period we want, and then trim the weight.
        # Same goes for metric.end being after the time period we want.
        # only type "long" appears to be compatible with .value.millis
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"inline"} =
            "(doc['metric_data.end'] < end ? doc['metric_data.end'] : end) - " . 
            "(doc['metric_data.begin'] > begin ? doc['metric_data.begin'] : begin)";
    } elsif ($mode eq 'scripted-painless') {
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"value"}{"field"} = "metric_data.value";
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"lang"} = "painless";
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"params"}{"end"} = int $end;
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"params"}{"begin"} = int $begin;
        # The script must check to see if the metric.begin is earlier than the time period we want, and then trim the weight.
        # Same goes for metric.end being after the time period we want.
        # only type "long" appears to be compatible with .value.millis
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"source"}  = 
                        "long begin = doc['metric_data.begin'].value.millis < params.begin ? params.begin : doc['metric_data.begin'].value.millis;";
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"source"} .= 
                        "long end = doc['metric_data.end'].value.millis < params.end ? params.end : doc['metric_data.end'].value.millis;";
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"script"}{"source"} .= 
                        "return end - begin + 1;";
    } elsif ($mode eq 'fast') {
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"value"}{"field"} = "metric_data.value";
        $$req_ref{"aggs"}{"metric_avg"}{"weighted_avg"}{"weight"}{"field"} = "metric_data.duration";
    }
}

sub get_many_metric_results_from_ids {
    my $host = shift;
    my $begin = shift;
    my $end = shift;
    my $resolution = shift; # the number of results within $begin and $end
    my @metric_ids = @_;
    my $num_metric_ids = scalar @metric_ids;
    #printf "num_metric_ids: %d\n", $num_metric_ids;
    my @values; # where we store the results for each slot in the time domain
    my $msearch_req_json = "";
    #my $msearch_wavg_req_json = "";
    #my $msearch_partial_before_req_json = "";
    #my $msearch_partial_after_req_json = "";
    my $duration = int ($end - $begin) / $resolution;
    my $this_begin = int $begin;
    my $this_end = int $begin + $duration;
    # Build the msearch to get a weighted average for each sample we need for $resolution
    do {
        # This first request is for the weighted average, but does not include the documents
        # which are partially outside the time range we need.
        my $req_ref = $coder->decode($template);
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.end": { "lte": "' . $this_end . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.begin": { "gte": "' . $this_begin . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"terms": {"metric_data.id": ' . $coder->encode(\@metric_ids) . '}}');
        # Since we will only use the aggregation data, don't return any _source data
        $$req_ref{"size"} = 0;
        get_weighted_avg_agg($req_ref, $this_begin, $this_end, 'fast');
        my $index = get_index_basename . "metric_data";
        my $req_json = $coder->encode($req_ref);
        $msearch_req_json .= '{"index" : "' . $index . '" }' . "\n";
        $msearch_req_json .= "$req_json\n";

        # This second request is for the total weight of the previous weighted average.
        # We need this because we are going to recompute the weighted average by adding
        # a few more documents that are partially outside the time domain.
        $req_ref = $coder->decode($template);
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.end": { "lte": "' . $this_end . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.begin": { "gte": "' . $this_begin . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"terms": {"metric_data.id": ' . $coder->encode(\@metric_ids) . '}}');
        # Since we will only use the aggregation data, don't return any _source data
        $$req_ref{"size"} = 0;
        $$req_ref{'aggs'}{'total_weight'}{'sum'}{'field'} = "metric_data.duration";
        $index = get_index_basename . "metric_data";
        $req_json = $coder->encode($req_ref);
        $msearch_req_json .= '{"index" : "' . $index . '" }' . "\n";
        $msearch_req_json .= "$req_json\n";

        # This third request is for documents that had its begin during or before the time range, but
        # its end was after the time range.
        $req_ref = $coder->decode($template);
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.end": { "gt": "' . $this_end . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.begin": { "lte": "' . $this_end . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"terms": {"metric_data.id": ' . $coder->encode(\@metric_ids) . '}}');
        $index = get_index_basename . "metric_data";
        $req_json = $coder->encode($req_ref);
        $msearch_req_json .= '{"index" : "' . $index . '" }' . "\n";
        $msearch_req_json .= "$req_json\n";

        # This fourth request is for documents that had its begin before the time range, but
        # its end was during or after the time range.
        $req_ref = $coder->decode($template);
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.end": { "gte": "' . $this_begin . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"range": {"metric_data.begin": { "lt": "' . $this_begin . '"}}}');
        push @{ $$req_ref{"query"}{"bool"}{"filter"} },
            $coder->decode('{"terms": {"metric_data.id": ' . $coder->encode(\@metric_ids) . '}}');
        $index = get_index_basename . "metric_data";
        $req_json = $coder->encode($req_ref);
        $msearch_req_json .= '{"index" : "' . $index . '" }' . "\n";
        $msearch_req_json .= "$req_json\n";

        $this_begin = int $this_end + 1;
        $this_end += int $duration + 1;
        if ($this_end > $end) {
            $this_end = int $end;
        }
    } until ($this_begin > $end);
    my $resp_json = es_get_query($host, "metric_data/metric_data/_msearch", $msearch_req_json, "Msearch, aggregate weighted average script to get value");
    my $resp_ref = $coder->decode($resp_json);
    #debug_log(Dumper $resp_ref);
    $this_begin = int $begin;
    $this_end = int $begin + $duration;
    my $count = 0;
    my $sets = 0;
    my $elements = scalar @{ $$resp_ref{'responses'} };
    while ($count < $elements) { # Responses to be processed 4 at a time
        my $time_window_duration = $this_end - $this_begin + 1;
        my $total_weight_times_metrics = $time_window_duration * $num_metric_ids;
        #printf "time_window_duration: %d\n", $time_window_duration;
        #printf "total_weight for %d metrics ids: %d\n", $num_metric_ids, $total_weight_times_metrics;
        $sets++;
        my $agg_avg;
        my $agg_weight;
        my $agg_avg_times_weight;
        my $new_weight;
        $agg_avg = $$resp_ref{'responses'}[$count]{'aggregations'}{'metric_avg'}{'value'};
        if (defined $agg_avg) {
            # We have the weighted average for documents that don't overlap the time range,
            # but we need to combine that with the documents that are partially outside
            # the time range.  We need to know the total weight from the documents we
            # just finished in order to add the new documents and recompute the new weighted
            # average.
            $agg_weight = $$resp_ref{'responses'}[$count+1]{'aggregations'}{'total_weight'}{'value'};
            #print "From aggregation using documents 100% within the time range:\n";
            #printf "  average: %.2f\n", $agg_avg;
            #$agg_avg *= $num_metric_ids; # The weighted avg will not add up from different metrics, so we must do it here
                                      # This is for 'throughput' class metrics.  For other classess, this may need to 
                                      # be handled differently.
            #printf "  average x num_metric_ids: %.2f\n", $agg_avg;
            #printf "  weight: %.2f\n", $agg_weight;
            #$agg_weight *= $num_metric_ids;
            #printf "  weight x num_metric_ids: %.2f\n", $agg_weight;
            $agg_avg_times_weight = $agg_avg * $agg_weight;
            #printf "  average x weight: %.2f\n", $agg_avg_times_weight;
        } else {
            # It is possible that the aggregation returned no results because all of the documents
            # were partially outside the time domain.  This can happen when
            # 1) A  metric does not change during the entire test, and therefore only 1 document
            # is created with a huge duration with begin before the time range and after after the
            # time range.
            # 2) The time domain we have is really small because the resolution we are using is
            # very big.
            #
            # In eithr case, we have to set the average and total_weight to 0, and then the
            # recompuation of the weighted average [with the last two requests in this set, finding
            # all of th docs that are partially in the time domain] will work.
            $agg_avg = 0;
            $agg_weight = 0;
            $agg_avg_times_weight = 0;
        }
        # Process last 2 of the 4 response 'set'
        # Since these docs have a time range partially outside the time range we want,
        # we have to get a new, reduced duration and use that to agment our weighted average.
        #print "From query using documents partially outside the time range:\n";
        my $sum_value_times_weight = 0;
        my $sum_weight = 0;
        # It is possible to have the same document returned from the last two queries in this set of 4.
        # This can happen when the document's begin is before $this_begin *and* the document's end
        # if after $this_end.
        # You must not process the document twice.  Perform a consolidation by organizing by the 
        # returned document's '_id'
        my %partial_docs;
        for (my $k = 2; $k < 4; $k++) {
            for my $j (@{ $$resp_ref{'responses'}[$count + $k]{'hits'}{'hits'} }) {
                for my $key (keys %{ $$j{'_source'}{'metric_data'} }) {
                    $partial_docs{$$j{'_id'}}{$key} = $$j{'_source'}{'metric_data'}{$key};
                }
            }
        }
        # Now we can process %partial_docs
        for my $id (keys %partial_docs) {
            my $duration = $partial_docs{$id}{'duration'};
            if ($partial_docs{$id}{'begin'} < $this_begin) {
                $duration -= $this_begin - $partial_docs{$id}{'begin'};
            }
            if ($partial_docs{$id}{'end'} > $this_end) {
                $duration -= $partial_docs{$id}{'end'} - $this_end;
            }
            my $value_times_weight = $partial_docs{$id}{'value'} * $duration;
            $sum_value_times_weight += $value_times_weight;
            $sum_weight += $duration;
        }
        my $result = ($agg_avg_times_weight + $sum_value_times_weight) / ($total_weight_times_metrics);
        #printf "agg_avg: %.2f  agg_weight %d\n", $agg_avg, $agg_weight;
        #printf "extra_avg: %.2f  extra_weight %d\n", $sum_value_times_weight / $sum_weight, $sum_weight;
        #printf "weighted avg: %.2f\n", $result;
        $result *= $num_metric_ids;
        $result=FormatSigFigs($result,4);
        my %data_sample = ( 'begin' => $this_begin, 'end' => $this_end, 'value' => $result );
        #printf "weighted avg x num_metric_ids: %.2f\n", $result;
        #push @values, $result;
        push @values, \%data_sample;
        $count += 4;
        $this_begin = int $this_end + 1;
        $this_end += int $duration + 1;
        if ($this_end > $end) {
            $this_end = int $end;
        }
    }
    debug_log("processed $sets\n");
    return @values;
}

sub get_metric_data {
    my $host = shift;
    my $data_ref = shift;
    my $begin = shift;
    my $end = shift;
    my $period_id = shift;
    my $metric_source = shift;
    my $metric_type = shift;
    my $resolution = shift;
    my @breakout = @_; 

    # If you are wanting just a single metric (no break-out, no data-series), then
    # $resolution should be 1 and $name_format should be blank.

    $$data_ref{'breakouts'} = '';
    $$data_ref{'values'} = ();
    my $aggs_json = get_aggregation_from_breakout($metric_source, $metric_type, @breakout);
    my $aggs_ref = $coder->decode($aggs_json);
    # create a new query with this aggregation
    my $metr_req_ref = $coder->decode($template);
    push @{ $$metr_req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"period.id": "' . $period_id . '"}}');
    push @{ $$metr_req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"metric_desc.source": "' . $metric_source . '"}}');
    push @{ $$metr_req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"metric_desc.type": "' . $metric_type . '"}}');
    while (scalar @breakout > 0) {
        my $field = shift(@breakout);
        my $value;
        #if ($field =~ /([^\=]+)\=([^\=]+)/) {
        if ($field =~ /([^\=]+)\=(.+)/) {
            $field = $1;
            $value = $2;
            push @{ $$metr_req_ref{"query"}{"bool"}{"filter"} },
                $coder->decode('{"term": {"metric_desc.names.' . $field . '": "' . $value . '"}}');
        }
    }
    $$metr_req_ref{"aggs"} = $$aggs_ref{"aggs"};
    $$metr_req_ref{"size"} = 0; # We don't need the source
    my $metr_req_json = $coder->encode($metr_req_ref);
    my $metr_resp = es_get_query($host, "metric_desc/metric_desc/_search", $metr_req_json, "Query to get all the metric groups (fio: result data per-host, per-job, per-IOtype)");
    #print $metr_resp;
    my $metr_resp_ref = $coder->decode($metr_resp);
    # by traversing the aggrgeations in the response, find all of the different metric groups
    # (each group represents a single timeseries).
    #
    # First traverse the aggregation response to build an array of filter_terms needed [in a query] to get the metric_desc document(s)
    my @metr_grp_terms = gen_metric_group_terms($$metr_resp_ref{"aggregations"}, "");
    #print "Metric search terms by group:\n", Dumper \@metr_grp_terms;
    # Maintain a hash of metric-group label (the name_format with values swapped in for field_names) to the filter terms query
    my %metr_terms_by_label;
    gen_label_to_terms(\%metr_terms_by_label,  @metr_grp_terms);
    for my $label (keys %metr_terms_by_label) {
        my @metric_ids = get_metric_ids_from_term($host, $period_id, $metr_terms_by_label{$label});
        my $duration = int ($end - $begin) / $resolution;
        my $this_begin = int $begin;
        my $this_end = int $begin + $duration;
        my @results = get_many_metric_results_from_ids($host, $begin, $end, $resolution, @metric_ids);
        $$data_ref{'values'}{$label} = \@results;
    }
    @breakout = sort(@breakout);
    my @metric_field_names = sort(get_name_format_field_names(get_name_format($host, $period_id, $metric_source, $metric_type)));
    my $diffed_field_names = Array::Diff->diff(\@breakout, \@metric_field_names);
    $$data_ref{'breakouts'} = $diffed_field_names->added;
}

# Build the aggregation-portion of a query (only agg, not including the boolean-filter-terms here)
# based on a metric_source, metric_type, and either all or a *subset* of the name_format
# that this metric uses.  For example, fio has one [of its many avail metrics] that has:
# metric_source: fio, metric_type: iops, name_format: %host%-%job%-%type% (type means io-type)
# if you call this function with the name_format = %host%-%job%-%type%, it will
# produce an aggregaton request that [when requested] will produce a nested response where
# every single of fio's host/job/[io-]type is returned individually -the deepest "bucket"
# in the response will have exactly one quantity.
# 
# However, if you were to use name_format = %host%-%job%, metrics from the same host and
# same job, but from different io-types would be grouped as one.
#
# Continue this trend and use name_format = %host%, and metric from the same host, but different
# jobs and io-types are grouped as one.
#
# Once you reach the point where name_format is blank, then all metrics are grouped as one.
# If you did not want to break-out the metric by anything at all, this is what you would do.
sub get_aggregation_from_name_format {
    my $name_format = shift;
    my $metric_source = shift;
    my $metric_type = shift;
    my $aggs_json = '{';
    # First build the nested aggregation first based on the metric_source and metric_type.
    # We do this in case there is no name_format provided (there is no break-out) for
    # the metrics, and we can still construct an aggregation.  The other option would
    # be to have no aggregaton at all, but then we need special code for that case, 
    # and it becomes more code mgmt, and not worth it.
    $aggs_json .= '"aggs": { "metric_desc.source": { "terms": { "field": "metric_desc.source" },';
    $aggs_json .= '"aggs": { "metric_desc.type": { "terms": { "field": "metric_desc.type" }';
    # Next build the nested aggregation based on the field names found in the name_format
    my @field_names;
    my $field_count = 0;
    while ( $name_format =~ /\%\S+\%/ ) {
        $name_format =~ s/([^\%]*)\%([^\%]+)\%(\.*)/$3/;
        my $field = $2;
        # strip off the '=value' if any
        $field =~ s/([\^=]+)\=([\^=]+)/$1/;
        push @field_names, $field;
        $field_count++;
        if ($field_count > 0) {
            $aggs_json .= ',';
        }
        # Build the nested aggregation: note the fewer number of }'s
        # The 'size' is bumped up to support much bigger aggregations
        # we need for large, nested metrics like CPU util for sar/mpstat
        # and per-PID CPU usage for pidstat.  Eventually this should be
        # 'composite' aggregations (if it can work while nested) or
        # mutliple queries.
        $aggs_json .= '"aggs": { "metric_desc.names.' . $2 . '": { "terms":' .
                      ' { "show_term_doc_count_error": true, "size": 1000,' .
                      ' "field": "metric_desc.names.' . $2 . '" }';
    }
    while ($field_count > 0) {
        $aggs_json .= "}}";
        $field_count--;
    }
    $aggs_json .= '}}}}}'; # extra closing brackets for metric_source/type aggs
    return $aggs_json;
}
sub get_aggregation_from_breakout {
    my $metric_source = shift;
    my $metric_type = shift;
    my @breakout = @_;
    my $aggs_json = '{';
    # First build the nested aggregation first based on the metric_source and metric_type.
    # We do this in case there is no name_format provided (there is no break-out) for
    # the metrics, and we can still construct an aggregation.  The other option would
    # be to have no aggregaton at all, but then we need special code for that case, 
    # and it becomes more code mgmt, and not worth it.
    $aggs_json .= '"aggs": { "metric_desc.source": { "terms": { "field": "metric_desc.source" },';
    $aggs_json .= '"aggs": { "metric_desc.type": { "terms": { "field": "metric_desc.type" }';
    # Next build the nested aggregation based on the field names found in the name_format
    my $field_count = 0;
    while (scalar @breakout > 0) {
        my $field = shift(@breakout);
        if ($field =~ /([^\=]+)\=([^\=]+)/) {
            $field = $1;
        }
        $field_count++;
        if ($field_count > 0) {
            $aggs_json .= ',';
        }
        # Build the nested aggregation: note the fewer number of }'s
        # The 'size' is bumped up to support much bigger aggregations
        # we need for large, nested metrics like CPU util for sar/mpstat
        # and per-PID CPU usage for pidstat.  Eventually this should be
        # 'composite' aggregations (if it can work while nested) or
        # mutliple queries.
        $aggs_json .= '"aggs": { "metric_desc.names.' . $field . '": { "terms":' .
                      ' { "show_term_doc_count_error": true, "size": 1000,' .
                      ' "field": "metric_desc.names.' . $field . '" }';
    }
    while ($field_count > 0) {
        $aggs_json .= "}}";
        $field_count--;
    }
    $aggs_json .= '}}}}}'; # extra closing brackets for metric_source/type aggs
    return $aggs_json;
}

# Find (recursively) all of the metric groups that exist for this name_format, return the
# filter terms that [when used in a query] could return the metric_desc document(s).
# This requires that you run get_aggregation_from_name_format() first, then run the
# query based on the nested aggregation returned from get_aggregation_from_name_format(), and then
# finally, you can call this function with the *response* from that query (but only the aggregation
# part of the response) 
sub gen_metric_group_terms {
    my $pointer = shift; # The aggregations section in the *response* from aggregation query that get_aggregation_from_name_format() formed.
    my $terms = shift; # The filter_terms that would return the correct metric_desc doc for this metric group (initially should be empty).
                       # These terms get constructed as this function is recursively called.
    my @metr_grp_queries;
    my $value;
    # If being called from a previous gen_metric_group_labels_terms, finish the second part of the terms query
    if (exists $$pointer{"key"}) {
        # This is the value for a field name from previous call to gen_metric_group_labels_terms() (see push statement below)
        $value = $$pointer{"key"};
        $terms .= '"' . $value . '"}}';
    }
    if (my @metr_desc = grep(/^metric_desc/, (keys %$pointer))) { 
        die 'Something went wrong, found more than one "metric_desc." in this scope of the aggregation response' if (scalar @metr_desc > 1);
        my $field = $metr_desc[0];
        if (exists $$pointer{$field} and exists $$pointer{$field}{"buckets"}) {
            foreach my $bucket (@{ $$pointer{$field}{"buckets"} }) {
                # Only the first half of the "term", the field name, is here because we need to go one level deeper to get
                # the value, in each of the buckets (one level deeper).
                push @metr_grp_queries, gen_metric_group_terms($bucket, $terms . "," . '{"term": {"' . $field . '": ');
            }
        }
        return @metr_grp_queries;
    } else {
        $terms =~ s/^,//;
        return $terms;
    }
}

sub gen_metric_source_types {
    my $pointer = shift; # The aggregations section in the *response* from aggregation query that get_aggregation_from_name_format() formed.
    my $terms = shift; # The filter_terms that would return the correct metric_desc doc for this metric group (initially should be empty).
                       # These terms get constructed as this function is recursively called.
    my @metr_grp_queries;
    my $value;
    # If being called from a previous gen_metric_group_labels_terms, finish the second part of the terms query
    if (exists $$pointer{"key"}) {
        # This is the value for a field name from previous call to gen_metric_group_labels_terms() (see push statement below)
        $value = $$pointer{"key"};
        $terms .= "-" . $value;
    }
    if (my @metr_desc = grep(/^metric_desc/, (keys %$pointer))) { 
        die 'Something went wrong, found more than one "metric_desc." in this scope of the aggregation response' if (scalar @metr_desc > 1);
        my $field = $metr_desc[0];
        if (exists $$pointer{$field} and exists $$pointer{$field}{"buckets"}) {
            foreach my $bucket (@{ $$pointer{$field}{"buckets"} }) {
                # Only the first half of the "term", the field name, is here because we need to go one level deeper to get
                # the value, in each of the buckets (one level deeper).
                push @metr_grp_queries, gen_metric_source_types($bucket, $terms);
            }
        }
        return @metr_grp_queries;
    } else {
        $terms =~ s/^,//;
        return $terms;
    }
}

sub gen_label_to_terms {
    my $metr_terms_by_label_ref = shift;
    my @metr_grp_terms = @_;
    # Example terms that might be used:
    #
    # [
    #  {"term": {"metric_desc.source": "fio"}},{"term": {"metric_desc.type": "iops"}}
    # ]
    #
    # [
    #  '{"term": {"metric_desc.source": "fio"}},{"term": {"metric_desc.type": "iops"}},{"term": {"metric_desc.names.host": "perf84"}},{"term": {"metric_desc.names.job": "1"}},{"term": {"metric_desc.names.type": "0"}}',
    #  '{"term": {"metric_desc.source": "fio"}},{"term": {"metric_desc.type": "iops"}},{"term": {"metric_desc.names.host": "perf84"}},{"term": {"metric_desc.names.job": "2"}},{"term": {"metric_desc.names.type": "0"}}',
    #  '{"term": {"metric_desc.source": "fio"}},{"term": {"metric_desc.type": "iops"}},{"term": {"metric_desc.names.host": "perf84"}},{"term": {"metric_desc.names.job": "3"}},{"term": {"metric_desc.names.type": "0"}}'
    # ]
    for my $term_json (@metr_grp_terms) {
        my $term_ref = $coder->decode('[' . $term_json . ']');
        my $label = "";
        for my $this_term (@$term_ref) {
            next if $$this_term{'term'}{'metric_desc.source'} or $$this_term{'term'}{'metric_desc.type'};
            for my $field_name (keys %{ $$this_term{"term"} }) { # Should be one field name
                $label .= '-' . $$this_term{"term"}{$field_name};
            }
        }
        $label =~ s/^-//;
        $$metr_terms_by_label_ref{$label} = $term_json;
    }
}

# With a period_id, query the metric_desc docs to return
# all unique combinations of 'metric_desc.source'-'metric_desc.type'.
# This represents all of the metrics available during this
# part of the benchmark-iteration-sample-period.
sub list_all_metrics {
    my $host = shift;
    my $begin = shift;
    my $end = shift;
    my $resolution = shift;
    my $period_id = shift;
    my $aggs_json = '{"aggs": { "metric_desc.source": { "terms": { "field": "metric_desc.source" },';
    $aggs_json .= '"aggs": { "metric_desc.type": { "terms": { "field": "metric_desc.type" }}}}}}';
    my $aggs_ref = $coder->decode($aggs_json);
    my $req_ref = $coder->decode($template);
    push @{ $$req_ref{"query"}{"bool"}{"filter"} },
        $coder->decode('{"term": {"period.id": "' . $period_id . '"}}');
    $$req_ref{"aggs"} = $$aggs_ref{"aggs"};
    $$req_ref{"size"} = 0; # We don't need the source
    my $req_json = $coder->encode($req_ref);
    my $resp_json = es_get_query($host, "metric_desc/metric_desc/_search", $req_json, "Query to aggregate all the metrics available");
    my $resp_ref = $coder->decode($resp_json);
    # The aggregations response is only 2 levels deeps, so we just
    # process here and don't use recursion like gen_metric_group_terms()
    for my $i (@{ $$resp_ref{'aggregations'}{'metric_desc.source'}{'buckets'} }) {
        my $source = $$i{'key'};
        printf "source: %s\n", $source;
        for my $j (@{ $$i{'metric_desc.type'}{'buckets'} }) {
            my $type = $$j{'key'};
            my $name_format = get_name_format($host, $period_id, $source, $type);
            my %data = ();
            get_metric_data($host, \%data, $begin, $end, $period_id, $source, $type, $resolution);
            my @field_names = get_name_format_field_names($name_format);
            printf "       type: %s  avail-break-outs: %s  values:\n", $type,  join(" ", @field_names);
            print  "             ", $coder->encode($data{'values'}{""}), "\n";
            #print Dumper \%data;
            #for my $label (sort keys %{ $data{'values'} }) {
                #$printf "                                    %s: %s\n", $label, join(" ", @{ $data{'values'}{$label} });
            #}
        }

    }
}

1;
