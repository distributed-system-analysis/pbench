if (typeof String.prototype.startsWith != 'function') {
    String.prototype.startsWith = function (str){
        return this.slice(0, str.length) == str;
    };
}
if (typeof String.prototype.endsWith != 'function') {
    String.prototype.endsWith = function (str){
        return this.slice(-str.length) == str;
    };
}

var _generate_1st_pass_stats = function(val, stats) {
    stats["count"] += 1;
    stats["sum"] += val;
    stats["sum_of_squares"] += (val * val);
    var min = stats["min"];
    if (min == null) {
        stats["min"] = val;
    }
    else if (min > val) {
        stats["min"] = val;
    }
    var max = stats["max"];
    if (max == null) {
        stats["max"] = val;
    }
    else if (max < val) {
        stats["max"] = val;
    }
    return val;
}

var _generate_2nd_pass_stats = function(stats, vals) {
    stats["avg"] = stats["sum"] / stats["count"];
    var avg = stats["avg"];
    var variance_sum = 0.0;
    for (var i = 0; i < vals.length; i++) {
        var val = vals[i].y;
        variance_sum += Math.pow((val - avg), 2);
    }
    var variance = variance_sum / stats["count"];
    stats["variance"] = variance;
    stats["std_deviation"] = Math.sqrt(variance);

    return null;
}

var _statistics_headings = [ "missing", "count", "min", "max", "sum", "avg", "sum_of_squares", "variance", "std_deviation" ];
var _initial_stats = function() {
    var stats = {};
    for (var i = 0, l = _statistics_headings.length; i < l; ++i) {
        var h = _statistics_headings[i];
        if (h == "count" || h == "missing") {
            stats[h] = 0;
        }
        else if (h == "min" || h == "max") {
            stats[h] = null;
        }
        else {
            stats[h] = 0.0;
        }
    }
    return stats;
}

var _max_series = 20;

var _empty_chart = function(msg) {
    return { 'data': [], 'start': new Date(), 'end': new Date(), 'stats': null, 'msg': msg };
}

var _process_csv_data = function(csv_data, threshold) {
    // This code assumes the .csv format is in one of two forms:
    //   1. ts, m0, m1, m2, ..., mN
    //   2. ts0, m0, ts1, m1, ts2, m2, ..., tsN, mN
    // And it also assumes that the label for each timestamp column is
    // "timestamp_ms", no matter how many are present

    var _keys = Object.keys(csv_data[0]);

    if (_keys.length <= 1) {
        return _empty_chart("No series data to graph for " + chart_file_name);
    }
    if (!_keys[0].startsWith("timestamp_") && !_keys[0].endsWith("_ms")) {
        return _empty_chart("Unrecognized .csv data file format for " + chart_file_name);
    }

    // We first transform the data into a hash table, below we make a slight
    // adjustment to put it into the array form nv.d3 expects.
    var _chart_datum = {};
    var _chart_datum_stats = {};
    var k, i, key, val;

    for (k = 0; k < _keys.length; k++) {
        key = _keys[k];
        if (key.startsWith("timestamp_") && key.endsWith("_ms")) continue;
        _chart_datum[key] = [];
        _chart_datum_stats[key] = _initial_stats();
    }

    if (_keys.length >= 4 && _keys[2].startsWith("timestamp_") && _keys[2].endsWith("_ms")) {
        if (_keys.length % 2 != 0) {
            return _empty_chart("Even number of columns expected for metrics with their own timestamps for " + chart_file_name);
        }
        // Assume: ts0, m0, ts1, m1, ts2, m2, ..., tsN, mN
        for (i = 1; i < csv_data.length; i++) {
            for (k = 1; k < _keys.length; k += 2) {
                key = _keys[k];
                if (key.startsWith("timestamp_") && key.endsWith("_ms")) {
                    return _empty_chart("Bug! " + chart_file_name);
                }
                val = csv_data[i][key];
                if (val == "") {
                    _chart_datum_stats[key]["missing"] += 1;
                    _chart_datum_stats[key]["count"] += 1;
                    continue;
                }
                _chart_datum[key].push([+csv_data[i]["timestamp_" + key + "_ms"],
                                        _generate_1st_pass_stats(+val, _chart_datum_stats[key])]);
            }
        }
    }
    else {
        // Assume: ts, m0, m1, m2, ..., mN
        for (i = 1; i < csv_data.length; i++) {
            for (k = 0; k < _keys.length; k++) {
                key = _keys[k];
                if (key == "timestamp_ms") continue;
                val = csv_data[i][key];
                if (val == "") {
                    _chart_datum_stats[key]["missing"] += 1;
                    _chart_datum_stats[key]["count"] += 1;
                    continue;
                }
                _chart_datum[key].push([+csv_data[i]["timestamp_ms"],
                                        _generate_1st_pass_stats(+val, _chart_datum_stats[key])]);
            }
        }
    }
    for (k = 0; k < _keys.length; k++) {
        key = _keys[k];
        if (key.startsWith("timestamp_") && key.endsWith("_ms")) continue;
        if (_chart_datum[key].length == 0) continue;
        _generate_2nd_pass_stats(_chart_datum_stats[key], _chart_datum[key]);
    }
    var _sorted_keys = [];
    for (k = 0; k < _keys.length; k++) {
        key = _keys[k];
        if (key.startsWith("timestamp_") && key.endsWith("_ms")) continue;
        _sorted_keys.push(key);
    }
    var _lcl_compare = function(a, b) {
        return (_chart_datum_stats[b]["avg"] - _chart_datum_stats[a]["avg"]);
    };
    // sort keys by avg
    _sorted_keys.sort(_lcl_compare);
    var chart_datum = {};
    chart_datum['stats'] = _chart_datum_stats;
    chart_datum['data'] = [];
    // Pick only the top _max_series
    for (k = 0; k < Math.min(_max_series, _sorted_keys.length); k++) {
        key = _sorted_keys[k];
        if (key.startsWith("timestamp_") && key.endsWith("_ms")) {
            return _empty_chart("Bug! " + chart_file_name);
        }
        // Guard against empty data sets
        if (_chart_datum[key].length == 0) continue;
        // Now we transform it into what nv.d3 expects.
        chart_datum.data.push({"key": key, "values": _chart_datum[key]});
    }

    var start = null, end = null, msg;
    if (chart_datum.data.length > 0) {
        msg = "";
        start = end = chart_datum.data[0].values[0][0];
        for (var i = 0; i < chart_datum.data.length; i++) {
            var vals = chart_datum.data[i].values;
            for (var j = 0; j < vals.length; j++) {
                var tval = vals[j][0];
                if (tval < start) start = tval;
                if (tval > end) end = tval;
            }
        }
    }
    else {
        msg = "No Data from any Series with Average over Threshold: " + d3.format(".3f")(threshold);
    }

    chart_datum['start'] = new Date(start);
    chart_datum['end'] = new Date(end);
    chart_datum['msg'] = msg;
    return chart_datum;
};

var colors = d3.scale.category20();
var keyColor = function(d, i) { return colors(d.key); };
var xAccessor = function(d) { return d[0]; };
var yAccessor = function(d) { return d[1]; };
var customTimeFormat = d3.time.format.multi([
    [".%L", function(d) { return d.getMilliseconds(); }],
    [":%S", function(d) { return d.getSeconds(); }],
    ["%I:%M", function(d) { return d.getMinutes(); }],
    ["%I %p", function(d) { return d.getHours(); }],
    ["%a %d", function(d) { return d.getDay() && d.getDate() != 1; }],
    ["%b %d", function(d) { return d.getDate() != 1; }],
    ["%B", function(d) { return d.getMonth(); }],
    ["%Y", function() { return true; }]
]);
var xTickFormat = function(d) { return customTimeFormat(new Date(d)); };
var yTickFormat = d3.format(',.3f');
var xLegendFormat = d3.time.format("%Y-%m-%dT%H:%M:%S");

var constructChart = function(graph_type, chartnum, chart_file_name, threshold) {
    // FIX-ME: For v0.2 based .html pages, display 'fetching' div overlaying graph
    d3.csv("csv/" + chart_file_name + ".csv", function (error, csv_data) {
        // FIX-ME: For v0.2 based .html pages, display 'rendering' div overlaying graph
        var chart_datum;
        if (error) {
            chart_datum = _empty_chart("No Data - there was an error loading the csv data from " + chart_file_name + ": " + error);
        }
        else {
            if (csv_data.length == 0) {
                chart_datum = _empty_chart("No data found for " + chart_file_name);
            }
            else {
                chart_datum = _process_csv_data(csv_data, threshold);
            }
        }

        var _chartnum = chartnum.toString();
        var chartid = "chart" + _chartnum;
        var saveid = "#save" + _chartnum;
        var thischart;
        var _graph_generator = function() {
            thischart = nv.models[graph_type]()
                .noData(chart_datum.msg)
                .xScale(d3.time.scale.utc())
                .x(xAccessor)
                .y(yAccessor)
                .useInteractiveGuideline(true)
                .color(keyColor);
            thischart.margin().left = 100;
            thischart.xAxis
                .axisLabel('Time (UTC) - ' + xLegendFormat(chart_datum.start) + ' to ' + xLegendFormat(chart_datum.end))
                .tickFormat(xTickFormat);
            thischart.yAxis
                // FIX-ME: Perhaps add a parameter for the Y-Axis legend?
                .tickFormat(yTickFormat);
            d3.select('#' + chartid)
                .datum(chart_datum.data)
                .call(thischart);

            // Resize the chart to include the entire legend.
            // FIX-ME: This should probably be an option in NVD3 legend objects.
            var current_height = parseInt(d3.select('svg#' + chartid).style('height'), 10);
            document.getElementById(chartid).style.height = String(current_height + thischart.legend.height()) + 'px';
            nv.utils.windowSize(thischart.update('height'));

            // Resize the chart when the browser window is resized.
            nv.utils.windowResize(thischart.update);

            return thischart;
        };
        var _graph_callback = function(_graph_) {
            // Called when graph has completed rendering.
            //console.log("Chart ID " + chartid + " for " + chart_file_name + " has finished rendering.");
            // FIX-ME: For v0.2 based .html pages, hide 'rendering' div overlaying graph
            d3.select(saveid).on("click", function() {
                saveSvgAsPng(document.getElementById(chartid), chart_file_name + ".png");
            });
        }
        nv.addGraph(_graph_generator, _graph_callback);
    });
};
