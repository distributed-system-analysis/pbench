
/*
  LPCPU (Linux Performance Customer Profiler Utility): ./tools/jschart.pm/jschart.js

  (C) Copyright IBM Corp. 2015

  This file is subject to the terms and conditions of the Eclipse
  Public License.  See the file LICENSE.TXT in this directory for more
  details.
*/

// This is a Javascript library that renders SVG charts.
//
// This library depends on 3 external packages: d3.js, d3-queue.js, and saveSvgAsPng.js
// Those packages are available here or via npm:
//     https://github.com/mbostock/d3
//     https://github.com/d3/d3-queue
//     https://github.com/exupero/saveSvgAsPng

// debugging placeholder for development use
var debug = 0;

var margin = { top: 70, right: 87, bottom: 66, left: 65},
    legend_properties = { columns: 5, row_height: 30, margin: { top: 37 } },
    total_width = 1000,
    total_height = 510,
    width = total_width - margin.left - margin.right,
    height = total_height - margin.top - margin.bottom,
    pixels_per_letter = 7.2;

var dsv = d3.dsv(" ", "text/plain");

var table_format_print = d3.format(" ,.2f");

var tooltip_format_print = d3.format(" ,f");

var utc_time_format_print = d3.time.format.utc("%Y-%m-%d %H:%M:%S");

var utc_time_format_tick = d3.time.format.utc("%M:%S");

var local_time_format_print = d3.time.format("%Y-%m-%d %H:%M:%S");

var local_time_format_tick = d3.time.format("%M:%S");

var timezone_print = d3.time.format("UTC/GMT %Z");

var zoom_rate = 0.03;

// array to store objects for each chart, with references to often used variables
var chart_refs = [];

// queue to use for generating charts, 1 at a time to limit the total amount of concurrency
var chart_queue = d3_queue.queue(1);

function compute_stacked_median(datasets) {
    var foo = [];
    var bar = [];

    datasets.map(function(d) {
	    if (d.values === undefined) {
		return null;
	    }

	    d.values.map(function(c) {
		    if (foo[c.x] === undefined) {
			foo[c.x] = 0;
		    }
		    foo[c.x] += c.y;
		});
	});

    for (var key in foo) {
	bar.push(foo[key]);
    }

    if (bar.length > 0) {
	return d3.median(bar);
    } else {
	return "No Samples";
    }
}

function id_str_fixup(string) {
    return string.replace(/[\[\]\s%.\/():,]/g, "_");
}

function mycolors(index) {
    var colors = [ "#FF0000", "#009900", "#0000FF", "#FF00FF", "#E69900", "#AC3839", "#00FFFF", "#007D00", "#00CACD", "#AA44AA",
		   "#FFFF00", "#C0C0FF", "#FF8000", "#00FF00", "#C0C000", "#1E90FF", "#778899", "#CD3278", "#808080", "#D2691E",
		   "#AAAAAA", "#FF9900", "#0033CC", "#400099", "#FFE500", "#B36B00", "#00248F", "#2D006B", "#B3A000", "#FFCC80",
		   "#809FFF", "#B580FF", "#FFF280", "#25F200", "#ED004B", "#FF6D00", "#008CA1", "#1AAA00", "#A60035", "#B34C00",
		   "#006270", "#BFF7FF", "#93FF80", "#FF80A8", "#FFB680", "#80EEFF", "#FF0E00", "#00C41B", "#00F9BA", "#0059BA",
		   "#FF8700", "#008913", "#003E82", "#B35F00", "#FF8780", "#80FF91", "#80BCFF", "#FFC380", "#00F610", "#0F7EF0",
		   "#D8FE00", "#FF0700", "#399E3F", "#3E6B9B", "#93A33A", "#A43D3B", "#007B08", "#023C78", "#6C7F00", "#800300",
		   "#15F824", "#2389F3", "#DBFE16", "#FF1C16", "#27F834", "#3391F3", "#DEFE28", "#DEFE28" ];

    return colors[(index % (colors.length - 1))];
}

function parse_plot_file(data_model, datasets, index, text) {
    var histogram = { samples: 0,
		      sum: 0,
		      mean: null,
		      median: null,
		      min: null,
		      max: null,
		      p90: null,
		      p95: null,
		      p99: null,
		      p9999: null
		    };

    var data = dsv.parseRows(text).map(function(row) {
	    var index = row[0].indexOf("#LABEL:");

	    if (index == -1) {
		if (data_model == "histogram") {
		    histogram.samples += +row[1];
		    histogram.sum += (+row[0] * +row[1]);
		}
		return { x: +row[0], y: +row[1] };
	    } else {
		var tmp = row[0].substring(7);
		row.shift();
		row.map(function(d) {
			tmp = tmp + " " + d;
		    });

		return { title: tmp };
	    }
	});

    var dataset_title = data[0].title;

    data.shift();

    var mean;
    var median;

    if (data.length > 0) {
	mean = d3.mean(data, function(d) { return d.y; });
	median = d3.median(data, function(d) { return d.y; });

	if (data_model == "histogram") {
	    histogram.mean = histogram.sum / histogram.samples;
	    histogram.min = data[0].x;
	    histogram.max = data[data.length - 1].x;

	    var count = 0;
	    var threshold = histogram.samples * 0.5;
	    var threshold_p90 = histogram.samples * 0.9;
	    var threshold_p95 = histogram.samples * 0.95;
	    var threshold_p99 = histogram.samples * 0.99;
	    var threshold_p9999 = histogram.samples * 0.9999;
	    for (var i=0; i < data.length; i++) {
		count += data[i].y;
		if ((histogram.median === null) && (count >= threshold)) {
		    histogram.median = data[i].x;
		}
		if ((histogram.p90 === null) && (count >= threshold_p90)) {
		    histogram.p90 = data[i].x;
		}
		if ((histogram.p95 === null) && (count >= threshold_p95)) {
		    histogram.p95 = data[i].x;
		}
		if ((histogram.p99 === null) && (count >= threshold_p99)) {
		    histogram.p99 = data[i].x;
		}
		if ((histogram.p9999 === null) && (count >= threshold_p9999)) {
		    histogram.p9999 = data[i].x;
		}
	    }
	}
    } else {
	mean = "No Samples";
	median = "No Samples";

	if (data_model == "histogram") {
	    histogram.mean = "No Samples";
	    histogram.median = "No Samples";
	    histogram.min = "No Samples";
	    histogram.max = "No Samples";
	    histogram.p90 = "No Samples";
	    histogram.p95 = "No Samples";
	    histogram.p99 = "No Samples";
	    histogram.p9999 = "No Samples";
	}
    }

    datasets[index] = {
	index: index,
	name: dataset_title,
	mean: mean,
	median: median,
	histogram: histogram,
	highlighted: false,
	dom: {
	    table_row: null,
	    path: null,
	    points: null,
	    legend: {
		rec: null,
		label: null
	    },
	},
	values: data.map(function(d) {
		return { x: d.x, y: d.y };
	    })
    };
}

function update_chart(data_model, chart_title, myobject, svg, datasets, location, stacked, stack, area, line, x, y, x_brush, y_brush, x2, y2, x_slider, y_slider, x_axis, y_axis, x2_axis, y2_axis) {
    var last_timestamp = 0;
    if (datasets.length) {
	last_timestamp = datasets[0].last_timestamp;
    }

    var post_data = "time=" + last_timestamp;

    if (myobject.json_args !== undefined) {
	post_data += "&" + myobject.json_args;
    }

    d3.json(myobject.json_plotfile)
	.header("Content-Type", "application/x-www-form-urlencoded")
	.post(post_data, function(error, json) {
	    if ((json !== undefined) &&
		(json.data_series_names !== undefined) &&
		(json.x_axis_series !== undefined) &&
		(json.data !== undefined)) {
		var timebase = new Date().getTime() / 1000;

		var table = d3.select("#" + location + "_table");

		var stacked_mean = 0;
		var valid_stacked_mean = 0;

		var x_axis_index = 0;
		for (var index=0; index<json.data_series_names.length; index++) {
		    if (json.data_series_names[index] === json.x_axis_series) {
			x_axis_index = index;
		    }
		}

		for (var index=0,dataset_index=0; index<json.data_series_names.length; index++) {
		    if (x_axis_index == index) {
			continue;
		    }

		    json.data.map(function(d) {
			datasets[dataset_index].values.push({ timestamp: d[0], x: 0, y: d[index] });
			datasets[dataset_index].last_timestamp = d[0];
		    });

		    if (myobject.history_length !== undefined) {
			var length = datasets[dataset_index].values.length;

			if (length > myobject.history_length) {
			    datasets[dataset_index].values.splice(0, length - myobject.history_length);
			}
		    }

		    datasets[dataset_index].values.map(function(d) {
			d.x = d.timestamp - timebase;
		    });

		    var mean;
		    var median;

		    if (datasets[dataset_index].values.length > 0) {
			mean = d3.mean(datasets[dataset_index].values, function(d) { return d.y; });
			median = d3.median(datasets[dataset_index].values, function(d) { return d.y });

			stacked_mean += mean;
			valid_stacked_mean = 1;
		    } else {
			mean = "No Samples";
			median = "No Samples"
		    }

		    datasets[dataset_index].mean = mean;
		    datasets[dataset_index].median = median;

		    table.select("#" + location + "_tablerow_" + id_str_fixup(datasets[dataset_index].name) + "_mean").text(table_format_print(mean));
		    table.select("#" + location + "_tablerow_" + id_str_fixup(datasets[dataset_index].name) + "_median").text(table_format_print(median));
		    table.select("#" + location + "_tablerow_" + id_str_fixup(datasets[dataset_index].name) + "_samples").text(datasets[dataset_index].values.length);

		    dataset_index++;
		}

		if (stacked) {
		    if (valid_stacked_mean) {
			stacked_mean = table_format_print(stacked_mean);
		    } else {
			stacked_mean = "No Samples";
		    }
		    table.select("#" + location + "_table_stackedmean").text(stacked_mean);

		    var stacked_median = compute_stacked_median(datasets);
		    if (isFinite(stacked_median)) {
			stacked_median = table_format_print(stacked_median);
		    }
		    table.select("#" + location + "_table_stackedmedian").text(stacked_median);

		    datasets = stack(datasets);
		}

		x.domain([
		    d3.min(datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.x; }); }),
		    d3.max(datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.x; }); })
		]);

		if (stacked) {
		    y.domain([
			d3.min(datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y0; }); }),
			d3.max(datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y0 + v.y; }); })
		    ]);
		} else {
		    y.domain([
			d3.min(datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y; }); }),
			d3.max(datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y; }); })
		    ]);
		}

		var domain = x.domain();

		if (myobject.x_min !== undefined) {
		    domain[0] = myobject.x_min;
		}

		if (myobject.x_max !== undefined) {
		    domain[1] = myobject.x_max;
		}

		x.domain(domain);
		x2.domain(x.domain());

		if (svg.select("#user_x_zoomed").text() == "0") {
		    x_brush.extent(domain);
		}

		var domain = y.domain();

		if (myobject.y_min !== undefined) {
		    domain[0] = myobject.y_min;
		}

		if (myobject.y_max !== undefined) {
		    domain[1] = myobject.y_max;
		}

		y.domain(domain);
		y2.domain(y.domain());

		if (svg.select("#user_y_zoomed").text() == "0") {
		    y_brush.extent(domain);
		}

		zoom_it(data_mode, 0, svg, x_brush, y_brush, x, y, x2, y2, x_slider, y_slider, x_axis, y_axis, x2_axis, y2_axis, stacked, area, line, location, myobject);
	    }
	});
}

function load_json(myobject, chart_title, datasets, callback) {
    var post_data = "";

    if (myobject.json_args !== undefined) {
	post_data += myobject.json_args;
    }

    d3.json(myobject.json_plotfile)
	.header("Content-Type", "application/x-www-form-urlencoded")
	.post(post_data, function(error, json) {
	    if ((json !== undefined) &&
		(json.data_series_names !== undefined) &&
		(json.x_axis_series !== undefined) &&
		(json.data !== undefined)) {
		var timebase = new Date().getTime() / 1000;

		var x_axis_index = 0;
		for (var index=0; index<json.data_series_names.length; index++) {
		    if (json.data_series_names[index] === json.x_axis_series) {
			x_axis_index = index;
		    }
		}

		for (var index=0,dataset_index=0; index<json.data_series_names.length; index++) {
		    if (index === x_axis_index) {
			continue;
		    }

		    datasets[dataset_index] = {
			index: index-1,
			name: json.data_series_names[index],
			mean: 0,
			median: 0,
			values: [],
			highlighted: false,
			dom: {
			    table_row: null,
			    path: null,
			    points: null,
			    legend: {
				rec: null,
				label: null
			    },
			},
			last_timestamp: 0
		    };

		    json.data.map(function(d) {
			datasets[dataset_index].values.push({ timestamp: d[x_axis_index], x: d[x_axis_index] - timebase, y: d[index] });
			datasets[dataset_index].last_timestamp = d[x_axis_index];
		    });

		    var mean;
		    var median;

		    if (datasets[dataset_index].values.length > 0) {
			mean = d3.mean(datasets[dataset_index].values, function(d) { return d.y; });
			median = d3.median(datasets[dataset_index].values, function(d) { return d.y; });
		    } else {
			mean = "No Samples";
			median = "No Samples";
		    }

		    datasets[dataset_index].mean = mean;
		    datasets[dataset_index].median = median;

		    dataset_index++;
		}
	    }

	    // signal that we are finished asynchronously loading the data
	    callback();
	});
}

function load_csv_files(url, data_model, chart_title, datasets, callback) {
    // the call to d3.text is performed asynchronously...queue.js
    // processing is used to ensure all files are loaded prior to
    // populating the graph, avoiding parallelism issues
    d3.text(url, "text/plain")
	.get(function(error, text) {
		if ((text === undefined) ||
		    (error !== null)) {
		    console.log("Error %O loading %s", error, url);

		    // create an error object with minimal properties
		    datasets[index] = {
			index: index,
			name: "Error loading " + url,
		    };

		    // signal that we are finished asynchronously failing to load the data
		    callback();
		    return;
		}

		var sample_counter = 0;
		var index_base = datasets.length;

		var data = d3.csv.parseRows(text).map(function(row) {
		    if (sample_counter == 0) {
			for (var i=1; i<row.length; i++) {
			    var histogram = { samples: 0,
					      sum: 0,
					      mean: null,
					      median: null,
					      min: null,
					      max: null,
					      p90: null,
					      p95: null,
					      p99: null,
					      p9999: null
					    };

			    datasets[index_base + i - 1] = {
				index: index_base + i - 1,
				name: row[i],
				mean: "No Samples",
				median: "No Samples",
				histogram: histogram,
				highlighted: false,
				dom: {
				    table_row: null,
				    path: null,
				    points: null,
				    legend: {
					rec: null,
					label: null
				    },
				},
				values: [],
			    };
			}
		    } else {
			for (var i=1; i<row.length; i++) {
			    if (row[i] == "") {
				continue;
			    }

			    datasets[index_base + i - 1].values.push({ x: +row[0], y: +row[i] });

			    if (data_model == "histogram") {
				datasets[index_base + i -1].histogram.samples += +row[i];
				datasets[index_base + i -1].histogram.sum += (+row[0] * +row[i]);
			    }
			}
		    }

		    sample_counter++;
		});

		for (var i=index_base; i<datasets.length; i++) {
		    if (datasets[i].values.length) {
			datasets[i].mean = d3.mean(datasets[i].values, function(d) { return d.y; });
			datasets[i].median = d3.median(datasets[i].values, function(d) { return d.y });

			if (data_model == "histogram") {
			    datasets[i].histogram.mean = datasets[i].histogram.sum / datasets[i].histogram.samples;
			    datasets[i].histogram.min = datasets[i].values[0].x;
			    datasets[i].histogram.max = datasets[i].values[datasets[i].values.length - 1].x;
			}

			var count = 0;
			var threshold = datasets[i].histogram.samples * 0.5;
			var threshold_p90 = datasets[i].histogram.samples * 0.9;
			var threshold_p95 = datasets[i].histogram.samples * 0.95;
			var threshold_p99 = datasets[i].histogram.samples * 0.99;
			var threshold_p9999 = datasets[i].histogram.samples * 0.9999;
			for (var p=0; p < datasets[i].values.length; p++) {
			    count += datasets[i].values[p].y;
			    if ((datasets[i].histogram.median === null) && (count >= threshold)) {
				datasets[i].histogram.median = datasets[i].values[p].x;
			    }
			    if ((datasets[i].histogram.p90 === null) && (count >= threshold_p90)) {
				datasets[i].histogram.p90 = datasets[i].values[p].x;
			    }
			    if ((datasets[i].histogram.p95 === null) && (count >= threshold_p95)) {
				datasets[i].histogram.p95 = datasets[i].values[p].x;
			    }
			    if ((datasets[i].histogram.p99 === null) && (count >= threshold_p99)) {
				datasets[i].histogram.p99 = datasets[i].values[p].x;
			    }
			    if ((datasets[i].histogram.p9999 === null) && (count >= threshold_p9999)) {
				datasets[i].histogram.p9999 = datasets[i].values[p].x;
			    }
			}
		    }
		}

		// signal that we are finished asynchronously loading the data
		callback();
	    });
}

function load_plot_file(url, data_model, chart_title, datasets, callback) {
    load_plot_files(url, data_model, chart_title, datasets, -1, callback)
}

function load_plot_files(url, data_model, chart_title, datasets, index, callback) {
    // the call to d3.text is performed asynchronously...queue.js
    // processing is used to ensure all files are loaded prior to
    // populating the graph, avoiding parallelism issues
    d3.text(url, "text/plain")
	.get(function(error, text) {
		if ((text === undefined) ||
		    (error !== null)) {
		    console.log("Error %O loading %s", error, url);

		    // create an error object with minimal properties
		    datasets[index] = {
			index: index,
			name: "Error loading " + url,
		    };

		    // signal that we are finished asynchronously failing to load the data
		    callback();
		    return;
		}

		var packed_separator = "--- JSChart Packed Plot File V1 ---";
		var packed_index = text.indexOf(packed_separator);
		var prev_packed_index = packed_index;
		if ((packed_index == -1) && (index >= 0)) {
		    parse_plot_file(data_model, datasets, index, text);
		} else {
		    var dataset_index = 0;

		    while (packed_index >= 0) {
			prev_packed_index = packed_index;
			packed_index = text.indexOf(packed_separator, packed_index+1);

			parse_plot_file(data_model, datasets, dataset_index++, text.slice(prev_packed_index + packed_separator.length + 1, packed_index));
		    }
		}

		// signal that we are finished asynchronously loading the data
		callback();
	    });
}

function create_download(filename, mime, charset, contents) {
    if (window.navigator.msSaveBlob) {
	// Internet Explorer path (tested on IE10 on Windows7)
	var blob = new Blob([contents], {
		type: mime + ";charset=" + charset + ";"
	    });
	window.navigator.msSaveBlob(blob, filename);
    } else {
	// Chrome / Firefox path (tested on Chrome 38 & Firefox ESR 31.1.0)
	var download = document.createElement('a');
	download.setAttribute('href', 'data:' + mime + ';charset=' + charset + ',' + encodeURIComponent(contents));
	download.setAttribute('download', filename);
	document.body.appendChild(download);
	download.click();
	document.body.removeChild(download);
    }
}

function navigate_to_chart(target) {
    var tgt = d3.select("#" + target);
    if (tgt[0][0]) {
	window.scrollTo(0, tgt[0][0].offsetTop);
    }
}

function complete_graph(stacked, data_model, x, x_axis, x2, x_axis2, y, y_axis, y2, y_axis2, svg, datasets, line, area, stack, myobject, location, chart_refs_index) {
    x.domain([
	      d3.min(datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.x; }); }),
	      d3.max(datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.x; }); })
	      ]);

    var domain = x.domain();

    if (isNaN(domain[0])) {
	domain[0] = 0;
    }

    if (isNaN(domain[1])) {
	domain[1] = 1;
    }

    // ensure that the domain is not "empty"
    if (domain[0] == domain[1]) {
	domain[0] *= 0.95;
	domain[1] *= 1.05;

	if (domain[0] == domain[1]) {
	    domain[1]++;
	}
    }

    if (myobject.x_min !== undefined) {
	domain[0] = myobject.x_min;
    }

    if (myobject.x_max !== undefined) {
	domain[1] = myobject.x_max;
    }

    x.domain(domain);
    x2.domain(x.domain());

    var legend_columns = legend_properties.columns;
    if (datasets.length < legend_properties.columns) {
	legend_columns = datasets.length;
    }

    var legend = svg.selectAll(".legend")
        .data(datasets)
	.enter().append("g")
        .attr("class", "legend")
        .attr("transform", function(d, i) { return "translate(" + (-margin.left + 5 + (i % legend_columns) * (total_width / legend_columns)) + "," + (height + legend_properties.margin.top + (Math.floor(i / legend_columns) * legend_properties.row_height)) + ")"; });

    legend.append("rect")
	.attr("class", "legendrect")
	.attr("id", function(d) { d.dom.legend.rect = this; return location + "_rect_" + id_str_fixup(d.name); })
	.attr("onclick", function(d) { return "click_highlight_function(" + chart_refs_index + ", " + d.index + ", " + stacked + ")"; })
	.attr("ondblclick", function(d) { return "console.log(chart_refs[" + chart_refs_index + "]); console.log(chart_refs[" + chart_refs_index + "].datasets[" + d.index + "])"; })
	.attr("onmouseover", function(d) { return "mouseover_highlight_function(" + chart_refs_index + ", " + d.index + ", " + stacked + ")"; })
	.attr("onmouseout", function(d) { return "mouseout_highlight_function(" + chart_refs_index + ", " + d.index + ", " + stacked + ")"; })
	.attr("width", 16)
	.attr("height", 16)
	.style("outline-color", function(d) { return mycolors(d.index); } )
	.style("fill", function(d) { return mycolors(d.index); } );

    var legend_label_offset = 25;

    legend.append("text")
	.attr("class", "legendlabel")
	.attr("id", function(d) { d.dom.legend.label = this; return location + "_label_" + id_str_fixup(d.name); })
	.attr("onclick", function(d) { return "click_highlight_function(" + chart_refs_index + ", " + d.index + ", " + stacked + ")"; })
	.attr("onmouseover", function(d) { return "mouseover_highlight_function(" + chart_refs_index + ", " + d.index + ", " + stacked + ")"; })
	.attr("onmouseout", function(d) { return "mouseout_highlight_function(" + chart_refs_index + ", " + d.index + ", " + stacked + ")"; })
	.attr("x", legend_label_offset)
	.attr("y", 13.5)
	.text(function(d) { return d.name; });

    svg.selectAll(".legendlabel")
	.each(function(d, i) {
		var label_width = this.getBBox().width;

		if (label_width >= (total_width / legend_columns - legend_label_offset)) {
		    var label = d3.select(this);

		    label.text(d.substr(0, 21) + '...')
			.on("mouseover", tooltip_on)
			.on("mouseout", tooltip_off);
		}
	    });

    if (myobject.legend_entries !== undefined) {
	var legend_entries = svg.selectAll(".legendentries")
	    .data(myobject.legend_entries)
	    .enter().append("g")
	    .attr("class", "legend")
	    .attr("transform", function(d, i) { return "translate(" + (-margin.left + 5) + ", " + (height + legend_properties.margin.top + ((Math.floor(datasets.length / legend_columns) + i) * legend_properties.row_height)) + ")"; });

	legend_entries.append("text")
	    .attr("class", "legendlabel")
	    .attr("y", 13.5)
	    .attr("lengthAdjust", "spacingAndGlyphs")
	    .attr("textLength", function(d, i) { if ((d.length * pixels_per_letter) >= total_width) { return (total_width - 5).toFixed(0); } })
	    .text(function(d) { return d; });
    }

    var errors = 0;

    // since the legend has been processed, remove any datasets that failed to load prior to creating the chart entries
    var loop = 1;
    while(loop) {
	loop = 0;

	for(var i=0; i<datasets.length; i++) {
	    if (datasets[i].values === undefined) {
		datasets.splice(i, 1);
		loop = 1;
		errors++;
		break;
	    }
	}
    }

    if (stacked) {
	datasets = stack(datasets);

	y.domain([
		  d3.min(datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y0; }); }),
		  d3.max(datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y0 + v.y; }); })
		  ]);
    } else {
	y.domain([
		  d3.min(datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y; }); }),
		  d3.max(datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y; }); })
		  ]);
    }

    var domain = y.domain();

    if (isNaN(domain[0])) {
	domain[0] = 0;
    }

    if (isNaN(domain[1])) {
	domain[1] = 1;
    }

    // ensure that the domain is not "empty"
    if (domain[0] == domain[1]) {
	domain[0] *= 0.95;
	domain[1] *= 1.05;

	if (domain[0] == domain[1]) {
	    domain[1]++;
	}
    }

    if (!stacked && domain[0] > 0) {
	domain[0] = 0;
    }

    domain[1] *= 1.05;

    if (myobject.y_min !== undefined) {
	domain[0] = myobject.y_min;
    }

    if (myobject.y_max !== undefined) {
	domain[1] = myobject.y_max;
    }

    y.domain(domain);
    y2.domain(y.domain());

    svg.select(".x.axis").call(x_axis);
    svg.select(".x2.axis").call(x_axis2);
    svg.select(".y.axis").call(y_axis);
    svg.select(".y2.axis").call(y_axis2);
    fix_y_axis_labels(svg);

    if (data_model == "timeseries") {
	set_x_axis_timeseries_label(svg, location, x.domain(), myobject.timeseries_timezone);
    }

    var plot;
    var group;
    var points;

    if (stacked) {
	plot = svg.selectAll(".plot")
	    .data(datasets)
	    .enter().append("g")
	    .attr("class", "plot")
	    .attr("id", function(d) { return location + "_group_" + id_str_fixup(d.name); });

	plot.append("path")
	    .attr("class", "area")
	    .attr("d", function(d) { d.dom.path = this; if (d.values === undefined) { return null; } return area(d.values); })
	    .style("fill", function(d) { return mycolors(d.index); })
	    .attr("clip-path", "url(#clip)")
	    .attr("id", function(d) { return location + "_area_" + id_str_fixup(d.name); });

	datasets.map(function(d) {
		if (d.values.length > 1) {
		    return;
		}

		group = svg.select("#" + location + "_group_" + id_str_fixup(d.name))
		    .append("g")
		    .attr("class", "points");

		group = group.selectAll(".points")
		    .data(d.values)
		    .enter().append("line")
		    .attr("class", "points")
		    .attr("id", function(b) { d.dom.points = this; return location + "_points_" + id_str_fixup(d.name); })
		    .attr("r", 3)
		    .attr("clip-path", "url(#clip)")
		    .style("stroke", mycolors(d.index))
		    .attr("x1", function(b) { return x(b.x); })
		    .attr("x2", function(b) { return x(b.x); })
		    .attr("y1", function(b) { return y(b.y0); })
		    .attr("y2", function(b) { return y(b.y + b.y0); });
	    });
    } else {
	plot = svg.selectAll(".plot")
	    .data(datasets)
	    .enter().append("g")
	    .attr("class", "plot")
	    .attr("id", function(d) { return location + "_group_" + id_str_fixup(d.name); });

	plot.append("path")
	    .attr("class", "line")
	    .attr("d", function(d) { d.dom.path = this; if (d.values === undefined) { return null; } return line(d.values); })
	    .style("stroke", function(d) { return mycolors(d.index) })
	    .attr("clip-path", "url(#clip)")
	    .attr("id", function(d) { return location + "_line_" + id_str_fixup(d.name); });

	datasets.map(function(d) {
		if (d.values.length > 1) {
		    return;
		}

		group = svg.select("#" + location + "_group_" + id_str_fixup(d.name))
		    .append("g")
		    .attr("class", "points");

		group = group.selectAll(".points")
		    .data(d.values)
		    .enter().append("circle")
		    .attr("class", "points")
		    .attr("id", function(b) { d.dom.points = this; return location + "_points_" + id_str_fixup(d.name); })
		    .attr("r", 3)
		    .attr("clip-path", "url(#clip)")
		    .style("fill", mycolors(d.index))
		    .style("stroke", mycolors(d.index))
		    .attr("cx", function(b) { return x(b.x); })
		    .attr("cy", function(b) { return y(b.y); });
	    });
    }

    return errors;
}

function create_table_controls(svg, location, myobject) {
    var table = document.getElementById(location + "_table");

    var colspan = 3;

    var table_header = d3.select(table).select("tr").select("th");

    if (table_header[0][0]) {
	colspan = table_header[0][0].colSpan;
    }

    var row = document.createElement("tr");
    row.id = location + "_tablerow_control_row_history";
    row.className = "footer";

    var cell = document.createElement("th");
    cell.id = location + "_tablerow_control_cell_history";
    cell.colSpan = colspan;
    cell.innerHTML = "History Length: ";

    var textbox = document.createElement("input");
    textbox.id = location + "_history_length";
    textbox.type = "text";
    if (myobject.history_length !== undefined) {
	textbox.value = myobject.history_length
    }

    cell.appendChild(textbox);

    var button = document.createElement("button")
    button.innerHTML = "Update";
    button.onclick = function() {
	var value = d3.select("#" + location + "_history_length")[0][0].value;
	if (!isNaN(value)) {
	    myobject.history_length = value;
	} else {
	    if (myobject.history_length !== undefined) {
		d3.select("#" + location + "_history_length")[0][0].value = myobject.history_length;
	    }
	}
    };

    cell.appendChild(button);

    row.appendChild(cell);

    table.appendChild(row);

    var row = document.createElement("tr");
    row.id = location + "_tablerow_control_row_interval";
    row.className = "footer";

    var cell = document.createElement("th");
    cell.id = location + "_tablerow_control_cell_interval";
    cell.colSpan = colspan;
    cell.innerHTML = "Update Interval: ";

    var textbox = document.createElement("input");
    textbox.id = location + "_update_interval";
    textbox.type = "text";
    if (myobject.update_interval !== undefined) {
	textbox.value = myobject.update_interval;
    }

    cell.appendChild(textbox);

    var button = document.createElement("button")
    button.innerHTML = "Update";
    button.onclick = function() {
	var value = d3.select("#" + location + "_update_interval")[0][0].value;
	if (!isNaN(value)) {
	    myobject.update_interval = value;
	    svg.select("#playpause")[0][0].__onclick();
	    svg.select("#playpause")[0][0].__onclick();
	} else {
	    if (myobject.update_interval !== undefined) {
		d3.select("#" + location + "_update_interval")[0][0].value = myobject.update_interval;
	    }
	}
    };

    cell.appendChild(button);

    row.appendChild(cell);

    table.appendChild(row);
}

function create_table_entries(data_model, chart_title, datasets, location, stacked, raw_data_sources, chart_refs_index) {
    var colspan;

    if (data_model == "histogram") {
	colspan = 10;
    } else {
	colspan = 4;
    }

    var table_cell = document.getElementById(location + "_table_cell");

    var table = document.createElement("table");
    table.id = location + "_table";
    table.className = 'chart';

    var table_header_1 = document.createElement("tr");
    table_header_1.className = 'header';

    var table_header_1_cell = document.createElement("th");
    table_header_1_cell.colSpan = colspan;
    table_header_1_cell.innerHTML = chart_title;

    table_header_1.appendChild(table_header_1_cell);
    table.appendChild(table_header_1);

    if (data_model == "histogram") {
	var table_header_2 = document.createElement("tr");
	table_header_2.className = 'header';

	var table_header_2_cell_1 = document.createElement("th");
	table_header_2_cell_1.align = 'left';
	table_header_2_cell_1.innerHTML = 'Data Sets';

	var table_header_2_cell_2 = document.createElement("th");
	table_header_2_cell_2.align = 'right';
	table_header_2_cell_2.innerHTML = 'Average';

	var table_header_2_cell_3 = document.createElement("th");
	table_header_2_cell_3.align = 'right';
	table_header_2_cell_3.innerHTML = 'Median';

	var table_header_2_cell_4 = document.createElement("th");
	table_header_2_cell_4.align = 'right';
	table_header_2_cell_4.innerHTML = 'Min';

	var table_header_2_cell_5 = document.createElement("th");
	table_header_2_cell_5.align = 'right';
	table_header_2_cell_5.innerHTML = 'Max';

	var table_header_2_cell_6 = document.createElement("th");
	table_header_2_cell_6.align = 'right';
	table_header_2_cell_6.innerHTML = '90%';

	var table_header_2_cell_7 = document.createElement("th");
	table_header_2_cell_7.align = 'right';
	table_header_2_cell_7.innerHTML = '95%';

	var table_header_2_cell_8 = document.createElement("th");
	table_header_2_cell_8.align = 'right';
	table_header_2_cell_8.innerHTML = '99%';

	var table_header_2_cell_9 = document.createElement("th");
	table_header_2_cell_9.align = 'right';
	table_header_2_cell_9.innerHTML = '99.99%';

	var table_header_2_cell_10 = document.createElement("th");
	table_header_2_cell_10.align = 'right';
	table_header_2_cell_10.innerHTML = 'Samples';

	table_header_2.appendChild(table_header_2_cell_1);
	table_header_2.appendChild(table_header_2_cell_2);
	table_header_2.appendChild(table_header_2_cell_3);
	table_header_2.appendChild(table_header_2_cell_4);
	table_header_2.appendChild(table_header_2_cell_5);
	table_header_2.appendChild(table_header_2_cell_6);
	table_header_2.appendChild(table_header_2_cell_7);
	table_header_2.appendChild(table_header_2_cell_8);
	table_header_2.appendChild(table_header_2_cell_9);
	table_header_2.appendChild(table_header_2_cell_10);

	table.appendChild(table_header_2);

	table_cell.appendChild(table);
    } else {
	var table_header_2 = document.createElement("tr");
	table_header_2.className = 'header';

	var table_header_2_cell_1 = document.createElement("th");
	table_header_2_cell_1.align = 'left';
	table_header_2_cell_1.innerHTML = 'Data Sets';

	var table_header_2_cell_2 = document.createElement("th");
	table_header_2_cell_2.align = 'right';
	table_header_2_cell_2.innerHTML = 'Data Set Average';

	var table_header_2_cell_3 = document.createElement("th");
	table_header_2_cell_3.align = 'right';
	table_header_2_cell_3.innerHTML = 'Data Set Median';

	var table_header_2_cell_4 = document.createElement("th");
	table_header_2_cell_4.align = 'right';
	table_header_2_cell_4.innerHTML = 'Samples';

	table_header_2.appendChild(table_header_2_cell_1);
	table_header_2.appendChild(table_header_2_cell_2);
	table_header_2.appendChild(table_header_2_cell_3);
	table_header_2.appendChild(table_header_2_cell_4);

	table.appendChild(table_header_2);

	table_cell.appendChild(table);
    }

    if (stacked) {
	var stacked_mean = 0;
	var valid_stacked_mean = 0;
    }

    datasets.map(function(d) {
	    var row = document.createElement("tr");
	    row.id = location + "_tablerow_" + id_str_fixup(d.name);
	    row.onclick = function() { click_highlight_function(chart_refs_index, d.index, stacked); };
	    row.onmouseover = function() { mouseover_highlight_function(chart_refs_index, d.index, stacked); };
	    row.onmouseout = function() { mouseout_highlight_function(chart_refs_index, d.index, stacked); };

	    var name_cell = document.createElement("td");
	    name_cell.align = "left";
	    name_cell.innerHTML = d.name;
	    row.appendChild(name_cell);

	    var mean_cell = document.createElement("td");
	    mean_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_mean";
	    mean_cell.align = "right";
	    if (data_model == "histogram") {
		if (isFinite(d.histogram.mean)) {
		    mean_cell.innerHTML = table_format_print(d.histogram.mean);
		} else {
		    mean_cell.innerHTML = d.histogram.mean;
		}
	    } else {
		if (isFinite(d.mean)) {
		    mean_cell.innerHTML = table_format_print(d.mean);
		} else {
		    mean_cell.innerHTML = d.mean;
		}
		if (stacked && (d.mean !== undefined) && isFinite(d.mean)) {
		    valid_stacked_mean = 1;
		    stacked_mean += d.mean;
		}
	    }
	    row.appendChild(mean_cell);

	    var median_cell = document.createElement("td");
	    median_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_median";
	    median_cell.align = "right";
	    if (data_model == "histogram") {
		if (isFinite(d.histogram.median)) {
		    median_cell.innerHTML = table_format_print(d.histogram.median);
		} else {
		    median_cell.innerHTML = d.histogram.median;
		}
	    } else {
		if (isFinite(d.median)) {
		    median_cell.innerHTML = table_format_print(d.median);
		} else {
		    median_cell.innerHTML = d.median;
		}
	    }
	    row.appendChild(median_cell);

	    if (data_model == "histogram") {
		var min_cell = document.createElement("td");
		min_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_min";
		min_cell.align = "right";
		if (isFinite(d.histogram.min)) {
		    min_cell.innerHTML = table_format_print(d.histogram.min);
		} else {
		    min_cell.innerHTML = d.histogram.min;
		}
		row.appendChild(min_cell);

		var max_cell = document.createElement("td");
		max_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_max";
		max_cell.align = "right";
		if (isFinite(d.histogram.max)) {
		    max_cell.innerHTML = table_format_print(d.histogram.max);
		} else {
		    max_cell.innerHTML = d.histogram.max;
		}
		row.appendChild(max_cell);

		var p90_cell = document.createElement("td");
		p90_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_p90";
		p90_cell.align = "right";
		if (isFinite(d.histogram.p90)) {
		    p90_cell.innerHTML = table_format_print(d.histogram.p90);
		} else {
		    p90_cell.innerHTML = d.histogram.p90;
		}
		row.appendChild(p90_cell);

		var p95_cell = document.createElement("td");
		p95_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_p95";
		p95_cell.align = "right";
		if (isFinite(d.histogram.p95)) {
		    p95_cell.innerHTML = table_format_print(d.histogram.p95);
		} else {
		    p95_cell.innerHTML = d.histogram.p95;
		}
		row.appendChild(p95_cell);

		var p99_cell = document.createElement("td");
		p99_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_p99";
		p99_cell.align = "right";
		if (isFinite(d.histogram.p99)) {
		    p99_cell.innerHTML = table_format_print(d.histogram.p99);
		} else {
		    p99_cell.innerHTML = d.histogram.p99;
		}
		row.appendChild(p99_cell);

		var p9999_cell = document.createElement("td");
		p9999_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_p9999";
		p9999_cell.align = "right";
		if (isFinite(d.histogram.p9999)) {
		    p9999_cell.innerHTML = table_format_print(d.histogram.p9999);
		} else {
		    p9999_cell.innerHTML = d.histogram.p9999;
		}
		row.appendChild(p9999_cell);
	    }

	    var sample_cell = document.createElement("td");
	    sample_cell.id = location + "_tablerow_" + id_str_fixup(d.name) + "_samples";
	    sample_cell.align = "right";
	    if (data_model == "histogram") {
		sample_cell.innerHTML = table_format_print(d.histogram.samples);
	    } else {
		sample_cell.innerHTML = table_format_print(d.values.length);
	    }

	    row.appendChild(sample_cell);

	    table.appendChild(row);

	    d.dom.table_row = row;
	});

    if (stacked) {
	var mean_row = document.createElement("tr");
	mean_row.className = "footer";

	var name_cell = document.createElement("th");
	name_cell.align = "left";
	name_cell.innerHTML = "Combined Average";
	mean_row.appendChild(name_cell);

	var mean_cell = document.createElement("td");
	mean_cell.id = location + "_table_stackedmean";
	mean_cell.align = "right";
	if (valid_stacked_mean) {
	    mean_cell.innerHTML = table_format_print(stacked_mean);
	} else {
	    mean_cell.innerHTML = "No Samples";
	}
	mean_row.appendChild(mean_cell);

	var blank_cell = document.createElement("td");
	blank_cell.innerHTML = "&nbsp;";
	mean_row.appendChild(blank_cell);

	if (colspan === 4) {
	    var blank_cell = document.createElement("td");
	    blank_cell.innerHTML = "&nbsp;";
	    mean_row.appendChild(blank_cell);
	}

	table.appendChild(mean_row);

	var median_row = document.createElement("tr");
	median_row.className = "footer";

	var name_cell = document.createElement("th");
	name_cell.align = "left";
	name_cell.innerHTML = "Combined Median";
	median_row.appendChild(name_cell);

	var blank_cell = document.createElement("td");
	blank_cell.innerHTML = "&nbsp;";
	median_row.appendChild(blank_cell);

	var median_cell = document.createElement("td");
	median_cell.id = location + "_table_stackedmedian";
	median_cell.align = "right";
	var stacked_median = compute_stacked_median(datasets);
	if (isFinite(stacked_median)) {
	    median_cell.innerHTML = table_format_print(stacked_median);
	} else {
	    median_cell.innerHTML = stacked_median;
	}
	median_row.appendChild(median_cell);

	if (colspan === 4) {
	    var blank_cell = document.createElement("td");
	    blank_cell.innerHTML = "&nbsp;";
	    median_row.appendChild(blank_cell);
	}

	table.appendChild(median_row);
    }

    if (raw_data_sources.length > 0) {
	var raw_sources_header_row = document.createElement("tr");
	raw_sources_header_row.className = "section";

	var label_cell = document.createElement("th");
	label_cell.align = "left";
	label_cell.colSpan = colspan;
	label_cell.innerHTML = "Raw Data Source(s):";
	raw_sources_header_row.appendChild(label_cell);

	table.appendChild(raw_sources_header_row);

	var raw_sources_content_row = document.createElement("tr");

	var content_cell = document.createElement("td");
	content_cell.colSpan = colspan;

	raw_data_sources.map(function(d) {
		var link = document.createElement("a");
		link.href = d;
		link.innerHTML = d.substr(d.lastIndexOf("/") + 1);

		content_cell.appendChild(link);
		content_cell.appendChild(document.createElement("br"));
		    });

	raw_sources_content_row.appendChild(content_cell);

	table.appendChild(raw_sources_content_row);
    }
}

function fix_y_axis_labels(svg) {
    var labels = svg.selectAll("g.y.axis,g.y2.axis").selectAll("g.tick").selectAll("text");

    labels.each(function(d, i) {
	    if ((this.getBBox().width + 10) >= margin.left) {
		var label = d3.select(this);
		label.on("mouseover", tooltip_on)
		    .on("mouseout", tooltip_off)
		    .attr("lengthAdjust", "spacingAndGlyphs")
		    .attr("textLength", margin.left - 10);
	    }
	});
}

function handle_brush_actions(data_model, svg, x_brush, y_brush, x, y, x2, y2, x_axis, y_axis, x_slider, y_slider, stacked, area, line, location, myobject) {
    if (x_brush.empty()) {
	x_brush.extent(x.domain());
    }

    if (y_brush.empty()) {
	y_brush.extent(y.domain());
    }

    var x_extent = x_brush.extent();
    var y_extent = y_brush.extent();

    var x_domain = x2.domain();
    var y_domain = y2.domain();

    x.domain(x_extent);
    y.domain(y_extent);

    svg.select("g.x.axis").call(x_axis);
    svg.select("g.y.axis").call(y_axis);

    x_slider.call(x_brush);
    y_slider.call(y_brush);

    if (stacked) {
	svg.selectAll("path.area").attr("d", function(d) { return area(d.values); });
	svg.selectAll("line.points").attr("x1", function(d) { return x(d.x) })
	    .attr("x2", function(d) { return x(d.x) })
	    .attr("y1", function(d) { return y(d.y0); })
	    .attr("y2", function(d) { return y(d.y + d.y0); });
    } else {
	svg.selectAll("path.line").attr("d", function(d) { return line(d.values); });
	svg.selectAll("circle.points").attr("cx", function(d) { return x(d.x) })
	    .attr("cy", function(d) { return y(d.y) });
    }

    fix_y_axis_labels(svg);

    if (data_model == "timeseries") {
	set_x_axis_timeseries_label(svg, location, x_extent, myobject.timeseries_timezone);
    }
}

function zoom_it(data_model, zoom, svg, x_brush, y_brush, x, y, x2, y2, x_slider, y_slider, x_axis, y_axis, x2_axis, y2_axis, stacked, area, line, location, myobject) {
    var x_extent = x_brush.extent();
    var x_domain = x2.domain();

    if (data_model == "timeseries") {
	// convert the timestamps into integers for the calculations that follow
	x_extent[0] = +x_extent[0];
	x_extent[1] = +x_extent[1];
	x_domain[0] = +x_domain[0];
	x_domain[1] = +x_domain[1];
    }
    var y_extent = y_brush.extent();
    var y_domain = y2.domain();

    var x_center = (x_extent[1] - x_extent[0]) / 2;
    var y_center = (y_extent[1] - y_extent[0]) / 2;

    x_extent[0] = x_extent[0] - (x_center * zoom);
    x_extent[1] = x_extent[1] + (x_center * zoom);

    y_extent[0] = y_extent[0] - (y_center * zoom);
    y_extent[1] = y_extent[1] + (y_center * zoom);

    if (x_extent[0] < x_domain[0]) {
	x_extent[0] = x_domain[0];
    }

    if (x_extent[1] > x_domain[1]) {
	x_extent[1] = x_domain[1];
    }

    if (y_extent[0] < y_domain[0]) {
	y_extent[0] = y_domain[0];
    }

    if (y_extent[1] > y_domain[1]) {
	y_extent[1] = y_domain[1];
    }

    if (x_extent[0] > x_extent[1]) {
	x_extent[0] = x_extent[0] + x_center - (x_center / 10000);
	x_extent[1] = x_extent[1] - x_center + (x_center / 10000);
    }

    if (y_extent[0] > y_extent[1]) {
	y_extent[0] = y_extent[0] + y_center - (y_center / 10000);
	y_extent[1] = y_extent[1] - y_center + (y_center / 10000);
    }

    if (data_model == "timeseries") {
	// convert the integers back into date objects after the calculations are complete
	x_extent[0] = new Date(Math.floor(x_extent[0]));
	x_extent[1] = new Date(Math.ceil(x_extent[1]));
    }

    x.domain(x_extent);
    y.domain(y_extent);

    x_brush.extent(x_extent);
    y_brush.extent(y_extent);

    svg.select("g.x.axis").call(x_axis);
    svg.select("g.y.axis").call(y_axis);

    svg.select("g.x2.axis").call(x2_axis);
    svg.select("g.y2.axis").call(y2_axis);

    x_slider.call(x_brush);
    y_slider.call(y_brush);

    if (stacked) {
	svg.selectAll("path.area").attr("d", function(d) { return area(d.values); });
	svg.selectAll("line.points").attr("x1", function(d) { return x(d.x) })
	    .attr("x2", function(d) { return x(d.x) })
	    .attr("y1", function(d) { return y(d.y0); })
	    .attr("y2", function(d) { return y(d.y + d.y0); });
    } else {
	svg.selectAll("path.line").attr("d", function(d) { return line(d.values); });
	svg.selectAll("circle.points").attr("cx", function(d) { return x(d.x) })
	    .attr("cy", function(d) { return y(d.y) });
    }

    fix_y_axis_labels(svg);

    if (data_model == "timeseries") {
	set_x_axis_timeseries_label(svg, location, x.domain(), myobject.timeseries_timezone);
    }
}
 
function generate_chart(stacked, data_model, location, chart_title, x_axis_title, y_axis_title, myobject, callback) {
    var datasets = [];

    if ((data_model == "xy") ||
	(data_model == "timeseries") ||
	(data_model == "histogram")) {
	console.log("User specified data_model=\"" + data_model + "\" for chart \"" + chart_title + "\"");
    } else {
	console.log("An unsupported data_model [\"" + data_model + "\"] was specified for chart \"" + chart_title + "\"");

	// signal that the chart generation is complete (albeit with an error)
	callback();
	return;
    }

    console.log("Beginning to build chart \"" + chart_title + "\"...");

    var div = document.getElementById(location);

    if (div == null) {
	console.log("Failed to locate div for \"" + chart_title + "\" identified by \"" + location + "\"");

	// signal that the chart generation is complete (albeit with an error)
	callback();
	return;
    }

    var table = document.createElement("table");

    var row = document.createElement("tr");
    row.vAlign = 'top';

    var chart_cell = document.createElement("td");
    chart_cell.id = location + "_chart";

    row.appendChild(chart_cell);

    var table_cell = document.createElement("td");
    table_cell.id = location + "_table_cell";

    row.appendChild(table_cell);

    table.appendChild(row);

    div.appendChild(table);

    var x;
    var x2;

    if ((data_model == "xy") ||
	(data_model == "histogram")) {
	x = d3.scale.linear();
	x2 = d3.scale.linear();
    } else if (data_model == "timeseries") {
	if ((myobject.timeseries_timezone !== undefined) &&
	    (myboject.timeseries_timezone === "local")) {
	    x = d3.time.scale();
	    x2 = d3.time.scale();
	} else {
	    myobject.timeseries_timezone = "utc";
	    x = d3.time.scale.utc();
	    x2 = d3.time.scale.utc();
	}
    }

    x.range([0, width]);

    x2.clamp(true)
	.range([0, width]);

    var y = d3.scale.linear()
	.range([height, 0]);

    var y2 = d3.scale.linear()
	.clamp(true)
	.range([height, 0]);

    var xAxis = d3.svg.axis()
	.scale(x)
	.orient("bottom")
	.tickSize(-height);

    var xAxis2 = d3.svg.axis()
	.scale(x2)
	.orient("top")
	.tickSize(9);

    if (data_model == "timeseries") {
	if (myobject.timeseries_timezone == "local") {
	    xAxis.tickFormat(local_time_format_tick);
	    xAxis2.tickFormat(local_time_format_tick);
	} else {
	    xAxis.tickFormat(utc_time_format_tick);
	    xAxis2.tickFormat(utc_time_format_tick);
	}
    }

    var xBrush = d3.svg.brush()
	.x(x2);

    var yAxis = d3.svg.axis()
	.scale(y)
	.orient("left")
	.tickSize(-width);

    var yAxis2 = d3.svg.axis()
	.scale(y2)
	.orient("right")
	.tickSize(9);

    var yBrush = d3.svg.brush()
	.y(y2);

    var line;
    var area;
    var stack;

    if (stacked) {
	area = d3.svg.area()
	    .x(function(d) { return x(d.x); })
	    .y0(function(d) { return y(d.y0); })
	    .y1(function(d) { return y(d.y0 + d.y); });

	stack = d3.layout.stack()
	    .values(function(d) { return d.values; });
    } else {
	line = d3.svg.line()
	    .x(function(d) { return x(d.x); })
	    .y(function(d) { return y(d.y); });
    }

    var extra_legend_rows = 0;
    if (myobject.legend_entries !== undefined) {
	extra_legend_rows = myobject.legend_entries.length;
    }

    var dataset_count = 0;
    if (myobject.packed !== undefined) {
	dataset_count = myobject.packed;
    } else {
	if (myobject.plotfiles !== undefined) {
	    dataset_count = myobject.plotfiles.length;
	}
    }

    var svg = d3.select("#" + location + "_chart").append("svg")
	.attr("class", "svg")
	.attr("id", location + "_svg")
	.attr("width", width + margin.left + margin.right)
	.attr("height", height + margin.top + margin.bottom + ((Math.ceil(dataset_count / legend_properties.columns) - 1 + extra_legend_rows) * legend_properties.row_height))
	.append("g")
	.attr("transform", "translate(" + margin.left + ", " + margin.top +")");

    svg.append("text")
	.attr("class", "hidden")
	.attr("id", "user_x_zoomed")
	.attr("x", 0)
	.attr("y", 0)
	.text("0");

    svg.append("text")
	.attr("class", "hidden")
	.attr("id", "user_y_zoomed")
	.attr("x", 0)
	.attr("y", 0)
	.text("0");

    svg.append("rect")
	.attr("class", "titlebox")
	.attr("x", -margin.left)
	.attr("y", -margin.top)
	.attr("width", width + margin.left + margin.right + 2)
	.attr("height", 15);

    svg.append("text")
	.attr("class", "title")
	.attr("x", (width/2))
	.attr("y", -margin.top + 11)
	.style("text-anchor", "middle")
	.text(chart_title);

    svg.append("text")
	.attr("class", "actionlabel")
	.attr("x", width + margin.right - 10)
	.attr("y", -margin.top + 29)
	.style("text-anchor", "end")
	.on("click", function() {
		x.domain(x2.domain());
		y.domain(y2.domain());

		xBrush.extent(x2.domain());
		yBrush.extent(y2.domain());

		svg.select("g.x.axis").call(xAxis);
		svg.select("g.y.axis").call(yAxis);

		svg.select("g.x2.axis").call(xAxis2);
		svg.select("g.y2.axis").call(yAxis2);

		x_slider.call(xBrush);
		y_slider.call(yBrush);

		if (stacked) {
		    svg.selectAll("path.area").attr("d", function(d) { return area(d.values); });
		    svg.selectAll("line.points").attr("x1", function(d) { return x(d.x) })
			.attr("x2", function(d) { return x(d.x) })
			.attr("y1", function(d) { return y(d.y0); })
			.attr("y2", function(d) { return y(d.y + d.y0); });
		} else {
		    svg.selectAll("path.line").attr("d", function(d) { return line(d.values); });
		    svg.selectAll("circle.points").attr("cx", function(d) { return x(d.x) })
			.attr("cy", function(d) { return y(d.y) });
		}

		fix_y_axis_labels(svg);

		if (data_model == "timeseries") {
		    set_x_axis_timeseries_label(svg, location, x.domain(), myobject.timeseries_timezone);
		}

		svg.selectAll("#user_x_zoomed,#user_y_zoomed").text("0");
	    })
	.text("Reset Zoom/Pan");

    var help = "This chart provides interactive features to assist the user in interpreting the data.\n\n";
    help += "You can \"lock\" a dataset to be hightlighted by clicking it in either the legend or the table to the right of the chart.  Click either entry to \"unlock\" the selection.\n\n";
    help += "When moving your mouse around the chart area, the coordinates will be displayed in the upper right part of the chart area.\n\n";
    help += "You can zoom into a selected area by clicking in the chart area and dragging the cursor to the opposite corner of the rectangular area you would like to focus on.  When you release the cursor the selection will be zoomed.\n\n";
    help += "You can also zoom in/out using the +/- controls which are visible when the mouse is over the chart area.\n\n";
    help += "You can control the panning and/or zooming using the slider controls above and to the right of the chart area.\n\n";
    help += "You can apply any x-axis zooming to all charts on the page by clicking the \"Apply X-Axis Zoom to All\" button (as long as the x-axis domains match).\n\n";
    help += "To reset the chart area to it's original state after being panned/zoomed, hit the \"Reset Zoom/Pan\" button in the upper right.\n\n";
    help += "You can download a CSV file for the data by clicking the \"Export Data as CSV\" button located under the chart title.  The exported data is limited by x-axis zooming, if performed.\n\n";
    help += "When the page has completed generating all charts, the background will change colors to signal that loading is complete.\n";

    svg.append("text")
	.attr("class", "actionlabel")
	.attr("x", (-margin.left/2))
	.attr("y", (height + 30))
	.attr("text-anchor", "middle")
	.on("click", function() {
		alert(help);
	    })
	.text("Help");

    svg.append("text")
	.attr("class", "actionlabel")
	.attr("x", (width / 3) * 2)
	.attr("y", -margin.top + 29)
	.style("text-anchor", "middle")
	.on("click", function() {
		saveSvgAsPng(document.getElementById(location + "_svg"), chart_title + ".png", {
		    backgroundColor: "#FFFFFF"
		});
	    })
	.text("Save as PNG");

    svg.append("text")
	.attr("class", "actionlabel")
	.attr("x", (width / 3))
	.attr("y", -margin.top + 29)
	.style("text-anchor", "middle")
	.on("click", function() {
		var string = "\"" + chart_title + "\"\n\"" + x_axis_title + "\"";
		var x_values = [];
		datasets.map(function(d) {
			string = string + ",\"" + d.name + " (" + y_axis_title + ")\"";

			// create a temporary placeholder for storing
			// the next index to start searching at below
			d.tmp_index = 0;

			d.values.map(function(b) {
				x_values.push(b.x);
			    });
		    });
		string = string + "\n";

		x_values.sort(function(a, b) { return a - b; });

		var x_domain = x.domain();

		for (var i=0; i<x_values.length; i++) {
		    // skip repeated x_values
		    if ((i > 0) && (x_values[i] == x_values[i-1])) {
			continue;
		    }

		    if ((x_values[i] >= x_domain[0]) &&
			(x_values[i] <= x_domain[1])) {
			string = string + x_values[i] + ",";

			for (var d=0; d<datasets.length; d++) {
			    //console.log("d=" + d);
			    for (var b=datasets[d].tmp_index; b<datasets[d].values.length; b++) {
				if (datasets[d].values[b].x == x_values[i]) {
				    string = string + datasets[d].values[b].y;
				    // store the next index to start searching at
				    datasets[d].tmp_index = b + 1;
				    break;
				}
			    }

			    string = string + ",";
			}

			string = string + "\n";
		    }
		}

		create_download(chart_title + '.csv', 'text/csv', 'utf-8', string);
	    })
	.text("Export Data as CSV");

    svg.append("text")
	.attr("class", "actionlabel")
	.attr("x", (width - 10))
	.attr("y", (height + 30))
	.attr("text-anchor", "middle")
	.on("click", function() {
		var x_domain = x.domain();

		chart_refs.map(function(d) {
			if (d.svg == svg) {
			    // skip applying zoom to myself
			    return;
			}

			var target_domain = d.x2.domain();
			var source_domain = x2.domain();

			var domain_check = 0;

			if (data_model == "timeseries") {
			    if (d.data_model == "timeseries") {
				if ((target_domain[0].getTime() !== source_domain[0].getTime()) ||
				    (target_domain[1].getTime() !== source_domain[1].getTime())) {
				    domain_check = 1;
				}
			    } else {
				domain_check = 1;
			    }
			} else {
			    if (d.data_model == "timeseries") {
				domain_check = 1;
			    } else {
				if ((target_domain[0] !== source_domain[0]) ||
				    (target_domain[1] !== source_domain[1])) {
				    domain_check = 1;
				}
			    }
			}

			if (domain_check) {
			    console.log("Skipping application of X-Axis zoom from \"" + chart_title + "\" to \"" + d.chart_title + "\" because data domains are not a match");
			    return;
			}

			d.x.domain(x_domain);

			d.x_brush.extent(x_domain);

			d.svg.select("g.x.axis").call(d.x_axis);

			d.x_slider.call(d.x_brush);

			if (d.stacked) {
			    d.svg.selectAll("path.area").attr("d", function(b) { return d.area(b.values); });
			    svg.selectAll("line.points").attr("x1", function(d) { return x(d.x) })
				.attr("x2", function(d) { return x(d.x) })
				.attr("y1", function(d) { return y(d.y0); })
				.attr("y2", function(d) { return y(d.y + d.y0); });
			} else {
			    d.svg.selectAll("path.line").attr("d", function(b) { return d.line(b.values); });
			    svg.selectAll("circle.points").attr("cx", function(d) { return x(d.x) })
				.attr("cy", function(d) { return y(d.y) });
			}

			fix_y_axis_labels(d.svg);
		    });
	    })
	.text("Apply X-Axis Zoom to All");

    svg.append("g")
	.attr("class", "x axis")
	.attr("transform", "translate(0," + height +")")
	.call(xAxis)
	.append("text")
	.attr("id", location + "_x_axis_label")
	.attr("class", "axislabel")
	.attr("y", 30)
	.attr("x", (width/2))
	.style("text-anchor", "middle")
	.text(x_axis_title);

    svg.append("g")
	.attr("class", "x2 axis")
	.attr("transform", "translate(0, -15)")
	.call(xAxis2);

    var x_arc = d3.svg.arc()
	.outerRadius(10)
	.startAngle(function(d, i) { if (i) { return Math.PI; } else { return 0; } })
	.endAngle(function(d, i) { if (i) { return 2 * Math.PI; } else { return Math.PI; } });

    var x_slider = svg.append("g")
	.attr("class", "x slider")
	.call(xBrush);

    x_slider.selectAll(".resize").append("path")
	.attr("transform", "translate(0, -15)")
	.attr("d", x_arc);

    x_slider.selectAll("rect")
	.attr("transform", "translate(0, -25)")
	.attr("height", 20);

    svg.append("g")
	.attr("class", "y axis")
	.call(yAxis)
	.append("text")
	.attr("id", location + "_y_axis_label")
	.attr("class", "axislabel")
	.attr("x", -margin.left + 10)
	.attr("y", -40)
	.style("text-anchor", "start")
	.text(y_axis_title);

    svg.append("g")
	.attr("class", "y2 axis")
	.attr("transform", "translate(" + (width + 15) + ", 0)")
	.call(yAxis2);

    var y_arc = d3.svg.arc()
	.outerRadius(10)
	.startAngle(function(d, i) { if (i) { return 0.5 * Math.PI; } else { return -0.5 * Math.PI; } })
	.endAngle(function(d, i) { if (i) { return 1.5 * Math.PI; } else { return 0.5 * Math.PI; } });

    var y_slider = svg.append("g")
	.attr("class", "y slider")
	.call(yBrush);

    y_slider.selectAll(".resize").append("path")
	.attr("transform", "translate(" + (width+15) + ", 0)")
	.attr("d", y_arc);

    y_slider.selectAll("rect")
	.attr("transform", "translate(" + (width + 5) + ", 0)")
	.attr("width", 20);

    var tmp_object  = { chart_title: chart_title,
			svg: svg,
			x: x,
			y: y,
			x2: x2,
			y2: y2,
			x_brush: xBrush,
			y_brush: yBrush,
			stacked: stacked,
			x_axis: xAxis,
			y_axis: yAxis,
			x2_axis: xAxis2,
			y2_axis: yAxis2,
			x_slider: x_slider,
			y_slider: y_slider,
			data_model: data_model,
			datasets: datasets,
			chart_selection: -1
    };
    if (stacked) {
	tmp_object.area = area;
    } else {
	tmp_object.line = line;
    }
    var chart_refs_index = chart_refs.push(tmp_object) - 1;

    xBrush.on("brush", function() {
	    if (d3.event.sourceEvent == null) {
		xBrush.extent(x.domain());
		x_slider.call(xBrush);
		return;
	    }

	    handle_brush_actions(data_model, svg, xBrush, yBrush, x, y, x2, y2, xAxis, yAxis, x_slider, y_slider, stacked, area, line, location, myobject);
	svg.select("#user_x_zoomed").text("1");
	});

    yBrush.on("brush", function() {
	    if (d3.event.sourceEvent == null) {
		yBrush.extent(y.domain());
		y_slider.call(yBrush);
		return;
	    }

	    handle_brush_actions(data_model, svg, xBrush, yBrush, x, y, x2, y2, xAxis, yAxis, x_slider, y_slider, stacked, area, line, location, myobject);
	svg.select("#user_y_zoomed").text("1");
	});

    svg.append("clipPath")
	.attr("id", "clip")
	.append("rect")
	.attr("x", x(0))
	.attr("y", y(1))
	.attr("width", x(1) - x(0))
	.attr("height", y(0) - y(1));

    var selection_start;
    var selection_stop;
    var selection_active = false;

    svg.append("rect")
	.attr("id", "pane")
	.attr("class", "pane")
	.attr("width", width)
	.attr("height", height)
	.on("mousedown", function() {
		if (d3.event.button != 0) {
		    return;
		}

		selection_start = d3.mouse(this);

		svg.select("#selection").remove();

		svg.insert("rect", "#coordinates")
		    .attr("id", "selection")
		    .attr("class", "selection")
		    .attr("x", 0)
		    .attr("y", 0)
		    .attr("width", 1)
		    .attr("height", 1)
		    .style("visibility", "hidden");

		selection_active = true;
	    })
	.on("mouseup", function() {
		if ((d3.event.button != 0) ||
		    !selection_active) {
		    return;
		}

		selection_stop = d3.mouse(this);

		svg.select("#selection").remove();

		selection_active = false;

		if ((selection_start[0] == selection_stop[0]) ||
		    (selection_start[1] == selection_stop[1])) {
		    return;
		}

		var x_extent = Array(0, 0), y_extent = Array(0, 0);

		if (selection_start[0] < selection_stop[0]) {
		    x_extent[0] = x.invert(selection_start[0]);
		    x_extent[1] = x.invert(selection_stop[0]);
		} else {
		    x_extent[0] = x.invert(selection_stop[0]);
		    x_extent[1] = x.invert(selection_start[0]);
		}

		if (selection_start[1] < selection_stop[1]) {
		    y_extent[1] = y.invert(selection_start[1]);
		    y_extent[0] = y.invert(selection_stop[1]);
		} else {
		    y_extent[1] = y.invert(selection_stop[1]);
		    y_extent[0] = y.invert(selection_start[1]);
		}

		xBrush.extent(x_extent);
		yBrush.extent(y_extent);

		x.domain(x_extent);
		y.domain(y_extent);

		svg.select("g.x.axis").call(xAxis);
		svg.select("g.y.axis").call(yAxis);

		x_slider.call(xBrush);
		y_slider.call(yBrush);

		if (stacked) {
		    svg.selectAll("path.area").attr("d", function(d) { return area(d.values); });
		    svg.selectAll("line.points").attr("x1", function(d) { return x(d.x) })
			.attr("x2", function(d) { return x(d.x) })
			.attr("y1", function(d) { return y(d.y0); })
			.attr("y2", function(d) { return y(d.y + d.y0); });
		} else {
		    svg.selectAll("path.line").attr("d", function(d) { return line(d.values); });
		    svg.selectAll("circle.points").attr("cx", function(d) { return x(d.x) })
			.attr("cy", function(d) { return y(d.y) });
		}

		fix_y_axis_labels(svg);

		if (data_model == "timeseries") {
		    set_x_axis_timeseries_label(svg, location, x_extent, myobject.timeseries_timezone);
		}

		if (data_model == "timeseries") {
		    if (myobject.timeseries_timezone == "local") {
			svg.select("#coordinates").style("visibility", "visible")
			    .text("x:" + local_time_format_print(x.invert(selection_stop[0])) + " y:" + table_format_print(y.invert(selection_stop[1])));
		    } else {
			svg.select("#coordinates").style("visibility", "visible")
			    .text("x:" + utc_time_format_print(x.invert(selection_stop[0])) + " y:" + table_format_print(y.invert(selection_stop[1])));
		    }
		} else {
		    svg.select("#coordinates").style("visibility", "visible")
			.text("x:" + table_format_print(x.invert(selection_stop[0])) + " y:" + table_format_print(y.invert(selection_stop[1])));
		}

		svg.selectAll("#user_x_zoomed,#user_y_zoomed").text("1");
	    })
	.on("mouseout", function() {
		svg.selectAll("#coordinates,#xcursorline,#ycursorline,#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		svg.select("#selection").remove();
		selection_active = false;
	    })
	.on("mousemove", function() {
		var mouse = d3.mouse(this);

		svg.selectAll("#zoomin,#zoomout,#playpause,#coordinates,#xcursorline,#ycursorline").style("visibility", "visible");

		if (data_model == "timeseries") {
		    if (myobject.timeseries_timezone == "local") {
			svg.select("#coordinates").text("x:" + local_time_format_print(x.invert(mouse[0])) + " y:" + table_format_print(y.invert(mouse[1])));
		    } else {
			svg.select("#coordinates").text("x:" + utc_time_format_print(x.invert(mouse[0])) + " y:" + table_format_print(y.invert(mouse[1])));
		    }
		} else {
		    svg.select("#coordinates").text("x:" + table_format_print(x.invert(mouse[0])) + " y:" + table_format_print(y.invert(mouse[1])));
		}

		svg.select("#xcursorline").attr("x1", mouse[0])
		    .attr("x2", mouse[0])
		    .attr("y1", y(y.domain()[1]))
		    .attr("y2", y(y.domain()[0]));

		svg.select("#ycursorline").attr("x1", x(x.domain()[0]))
		    .attr("x2", x(x.domain()[1]))
		    .attr("y1", mouse[1])
		    .attr("y2", mouse[1]);

		var selection = svg.select(".selection");

		if (selection.size() == 1) {
		    var selection_x, selection_y,
			selection_width, selection_height;

		    if (selection_start[0] < mouse[0]) {
			selection_x = selection_start[0];
			selection_width = mouse[0] - selection_start[0];
		    } else {
			selection_x = mouse[0];
			selection_width = selection_start[0] - mouse[0];
		    }

		    if (selection_start[1] < mouse[1]) {
			selection_y = selection_start[1];
			selection_height = mouse[1] - selection_start[1];
		    } else {
			selection_y = mouse[1];
			selection_height = selection_start[1] - mouse[1];
		    }

		    selection.attr("x", selection_x)
			.attr("y", selection_y)
			.attr("width", selection_width)
			.attr("height", selection_height)
			.style("visibility", "visible");
		}
	    });

    var loading = svg.append("text")
	.attr("class", "loadinglabel")
	.attr("x", x(0.5))
	.attr("y", y(0.5) + 35)
	.style("text-anchor", "middle")
	.text("Loading");

    // create a new queue object for loading datasets
    var async_q;

    //console.time("\"" + chart_title + "\" Data Load");

    if (myobject.csvfiles !== undefined) {
	// this path can have no parallelism since it is unknown how
	// many datasets each CSV file might contain
	async_q = d3_queue.queue(1);

	for (var i=0; i<myobject.csvfiles.length; i++) {
	    // add a dataset load to the queue
	    async_q.defer(load_csv_files, myobject.csvfiles[i], data_model, chart_title, datasets);
	}
    } else {
	// this path can have some parallelism, but place a limit on
	// it to keep things under control
	async_q = d3_queue.queue(512);

	if ((myobject.packed !== undefined) &&
	    (myobject.plotfile !== undefined)) {
	    // add a packed dataset load to the queue
	    async_q.defer(load_plot_file, myobject.plotfile, data_mode, chart_title, datasets);
	} else {
	    if (myobject.plotfiles !== undefined) {
		for (var i=0; i<myobject.plotfiles.length; i++) {
		    // add a dataset load to the queue
		    async_q.defer(load_plot_files, myobject.plotfiles[i], data_model, chart_title, datasets, i);
		}
	    } else {
		if (myobject.json_plotfile !== undefined) {
		    async_q.defer(load_json, myobject, chart_title, datasets);
		}
	    }
	}
    }

    // block waiting for the queue processing to complete before completing the chart
    async_q.await(function(error, results) {
	    //console.timeEnd("\"" + chart_title + "\" Data Load");

	    console.log("Content load complete for chart \"" + chart_title + "\".");

	    if (datasets.length > dataset_count) {
		console.log("Resizing SVG for chart \"" + chart_title + "\".");
		d3.select("#" + location + "_chart").select("svg").attr("height", height + margin.top + margin.bottom + ((Math.ceil(datasets.length / legend_properties.columns) - 1 + extra_legend_rows) * legend_properties.row_height))
	    }

	    console.log("Creating table entries for chart \"" + chart_title + "\"...");
	    if (myobject.raw_data_sources === undefined) {
		myobject.raw_data_sources = [];
	    }

	    create_table_entries(data_model, chart_title, datasets, location, stacked, myobject.raw_data_sources, chart_refs_index);
	    console.log("...finished adding table entries for chart \"" + chart_title + "\"");

	    if (myobject.update_interval !== undefined) {
		console.log("Creating table controls for chart \"" + chart_title + "\"...");
		create_table_controls(svg, location, myobject);
		console.log("...finished adding table controls for chart \"" + chart_title + "\"");
	    }

	    console.log("Processing datasets for chart \"" + chart_title + "\"...");
	    var errors = complete_graph(stacked, data_model, x, xAxis, x2, xAxis2, y, yAxis, y2, yAxis2, svg, datasets, line, area, stack, myobject, location, chart_refs_index);
	    console.log("...finished processing datasets for chart \"" + chart_title + "\"");

	    x_slider.call(xBrush.event);
	    y_slider.call(yBrush.event);

	    if (errors) {
		loading.text("Load Errors");
	    } else {
		loading.remove();
	    }

	    var zoomout = svg.append("g")
		.attr("id", "zoomout")
		.attr("class", "chartbutton")
		.style("visibility", "hidden")
		.on("click", function() {
		    zoom_it(data_model, zoom_rate, svg, xBrush, yBrush, x, y, x2, y2, x_slider, y_slider, xAxis, yAxis, xAxis2, yAxis2, stacked, area, line, location, myobject);
		    svg.selectAll("#user_x_zoomed,#user_y_zoomed").text("1");
		    })
		.on("mouseout", function() {
			svg.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		    })
		.on("mouseover", function() {
			svg.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "visible");
		    });

	    zoomout.append("circle")
		.attr("cx", 20)
		.attr("cy", 20)
		.attr("r", 11);

	    zoomout.append("text")
		.attr("x", 20)
		.attr("y", 24)
		.style("text-anchor", "middle")
		.text("-");

	    var zoomin = svg.append("g")
		.attr("id", "zoomin")
		.attr("class", "chartbutton")
		.style("visibility", "hidden")
		.on("click", function() {
		    zoom_it(data_model, -1 * zoom_rate, svg, xBrush, yBrush, x, y, x2, y2, x_slider, y_slider, xAxis, yAxis, xAxis2, yAxis2, stacked, area, line, location, myobject);
		    svg.selectAll("#user_x_zoomed,#user_y_zoomed").text("1");
		    })
		.on("mouseout", function() {
			svg.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		    })
		.on("mouseover", function() {
			svg.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "visible");
		    });

	    zoomin.append("circle")
		.attr("cx", 50)
		.attr("cy", 20)
		.attr("r", 11);

	    zoomin.append("text")
		.attr("x", 50)
		.attr("y", 24)
		.style("text-anchor", "middle")
		.text("+");

	    svg.append("line")
		.attr("id", "xcursorline")
		.attr("class", "cursorline")
		.attr("x1", 0)
		.attr("y1", 0)
		.attr("x2", 1)
		.attr("y2", 1)
		.style("visibility", "hidden");

	    svg.append("line")
		.attr("id", "ycursorline")
		.attr("class", "cursorline")
		.attr("x1", 0)
		.attr("y1", 0)
		.attr("x2", 1)
		.attr("y2", 1)
		.style("visibility", "hidden");

	    svg.append("text")
		.attr("id", "coordinates")
		.attr("class", "coordinates")
		.attr("x", width - 5)
		.attr("y", 15)
		.style("text-anchor", "end")
		.style("visibility", "hidden")
		.text("coordinates");

	    console.log("...finished building chart \"" + chart_title + "\"");

	    if ((myobject.update_interval !== undefined) &&
		(myobject.json_plotfile !== undefined)) {
		var interval = window.setInterval(function() {
		    update_chart(data_model, chart_title, myobject, svg, datasets, location, stacked, stack, area, line, x, y, xBrush, yBrush, x2, y2, x_slider, y_slider, xAxis, yAxis, xAxis2, yAxis2);
		}, myobject.update_interval * 1000);

		var live_update = true;

		var playpause = svg.append("g")
		    .attr("id", "playpause")
		    .attr("class", "chartbutton")
		    .style("visibility", "hidden")
		    .on("click", function () {
			if (live_update) {
			    live_update = false;
			    clearInterval(interval);
			    //svg.select("#playpauselabel").text("Play");
			} else {
			    live_update = true;
			    interval = window.setInterval(function() {
				update_chart(data_model, chart_title, myobject, svg, datasets, location, stacked, stack, area, line, x, y, xBrush, yBrush, x2, y2, x_slider, y_slider, xAxis, yAxis, xAxis2, yAxis2);
			    }, myobject.update_interval * 1000);
			    //svg.select("#playpauselabel").text("Pause");
			}
		    })
		    .on("mouseout", function() {
			svg.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		    })
		    .on("mouseover", function() {
			svg.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "visible");
		    });

		playpause.append("circle")
		    .attr("cx", 35)
		    .attr("cy", 45)
		    .attr("r", 11);

		playpause.append("polygon")
		    .attr("class", "playicon")
		    .attr("points", "29,42 29,49 34,45");

		playpause.append("line")
		    .attr("class", "pauseicon")
		    .attr("x1", 37)
		    .attr("y1", 41)
		    .attr("x2", 37)
		    .attr("y2", 50);

		playpause.append("line")
		    .attr("class", "pauseicon")
		    .attr("x1", 41)
		    .attr("y1", 41)
		    .attr("x2", 41)
		    .attr("y2", 50);
	    }

	    // signal that the chart generation is complete
	    callback();
	});
}

function create_graph(stacked, data_model, location, chart_title, x_axis_title, y_axis_title, myobject) {
    if (stacked === "stackedAreaChart") {
	stacked = 1;
    } else if (stacked === "lineChart") {
	stacked = 0;
    }

    // add an entry to the chart generating queue
    chart_queue.defer(generate_chart, stacked, data_model, location, chart_title, x_axis_title, y_axis_title, myobject);
}

function finish_page() {
    // wait for chart generation to complete before logging that it is done and changing the page background
    chart_queue.await(function(error, results) {
	    d3.select("body").style("background-color", "#CCCCCC");
	    console.log("Finished generating all charts");
	});
}

function click_highlight_function(chart_refs_index, datasets_index, stacked) {
    if ((chart_refs[chart_refs_index].chart_selection == -1) ||
	(chart_refs[chart_refs_index].chart_selection != datasets_index)) {
	if (chart_refs[chart_refs_index].chart_selection != -1) {
	    dehighlight(chart_refs_index, chart_refs[chart_refs_index].chart_selection, stacked);
	    chart_refs[chart_refs_index].datasets[chart_refs[chart_refs_index].chart_selection].highlighted = false;
	}
	chart_refs[chart_refs_index].datasets[datasets_index].highlighted = true;
	chart_refs[chart_refs_index].chart_selection = datasets_index;
	highlight(chart_refs_index, datasets_index, stacked);
    } else {
	chart_refs[chart_refs_index].datasets[datasets_index].highlighted = false;
	chart_refs[chart_refs_index].chart_selection = -1;
	highlight(chart_refs_index, datasets_index, stacked);
    }
}

function mouseover_highlight_function(chart_refs_index, datasets_index, stacked) {
    if (chart_refs[chart_refs_index].chart_selection == -1) {
	highlight(chart_refs_index, datasets_index, stacked);
    }
}

function mouseout_highlight_function(chart_refs_index, datasets_index, stacked) {
    if (chart_refs[chart_refs_index].chart_selection == -1) {
	dehighlight(chart_refs_index, datasets_index, stacked);
    }
}

function highlight(chart_refs_index, datasets_index, stacked) {
    d3.select(chart_refs[chart_refs_index].datasets[datasets_index].dom.legend.label).style("font-weight", "bold");

    if (stacked) {
	for (var i = 0; i < chart_refs[chart_refs_index].datasets.length; i++) {
	    if (i == datasets_index) {
		d3.select(chart_refs[chart_refs_index].datasets[i].dom.path).style("opacity", "0.9");

		d3.select(chart_refs[chart_refs_index].datasets[i].dom.points).style("opacity", "0.9")
		    .style("stroke-width", "5.0px");
	    } else {
		d3.select(chart_refs[chart_refs_index].datasets[i].dom.path).style("opacity", "0.15");

		d3.select(chart_refs[chart_refs_index].datasets[i].dom.points).style("opacity", "0.15");
	    }
	}
    } else {
	for (var i = 0; i < chart_refs[chart_refs_index].datasets.length; i++) {
	    if (i == datasets_index) {
		d3.select(chart_refs[chart_refs_index].datasets[i].dom.path).style("opacity", "0.9")
		    .style("stroke-width", "3.0px");

		d3.select(chart_refs[chart_refs_index].datasets[i].dom.path).style("opacity", "0.9")
		    .attr("r", 4);
	    } else {
		d3.select(chart_refs[chart_refs_index].datasets[i].dom.path).style("opacity", "0.15")
		    .style("stroke-width", "1.5px");

		d3.select(chart_refs[chart_refs_index].datasets[i].dom.points).style("opacity", "0.15");
	    }
	}
    }

    for (var i = 0; i < chart_refs[chart_refs_index].datasets.length; i++) {
	if (i == datasets_index) {
	    d3.select(chart_refs[chart_refs_index].datasets[i].dom.legend.rect).style("opacity", "0.9");
	} else {
	    d3.select(chart_refs[chart_refs_index].datasets[i].dom.legend.rect).style("opacity", "0.15");
	}
    }

    d3.select(chart_refs[chart_refs_index].datasets[datasets_index].dom.table_row).style("background-color", "black")
	.style("color", "white");
}

function dehighlight(chart_refs_index, datasets_index, stacked) {
    d3.select(chart_refs[chart_refs_index].datasets[datasets_index].dom.legend.label).style("font-weight", "normal");

    if (stacked) {
	for (var i = 0; i < chart_refs[chart_refs_index].datasets.length; i++) {
	    d3.select(chart_refs[chart_refs_index].datasets[i].dom.path).style("opacity", "0.9");

	    d3.select(chart_refs[chart_refs_index].datasets[i].dom.points).style("opacity", "0.9")
		.style("stroke-width", "3.0px");
	}
    } else {
	for (var i = 0; i < chart_refs[chart_refs_index].datasets.length; i++) {
	    d3.select(chart_refs[chart_refs_index].datasets[i].dom.path).style("opacity", "0.9")
		.style("stroke-width", "1.5px");

	    d3.select(chart_refs[chart_refs_index].datasets[i].dom.points).style("opacity", "0.9")
		.attr("r", 3);
	}
    }

    for (var i = 0; i < chart_refs[chart_refs_index].datasets.length; i++) {
	d3.select(chart_refs[chart_refs_index].datasets[i].dom.legend.rect).style("opacity", "0.9");
    }

    d3.select(chart_refs[chart_refs_index].datasets[datasets_index].dom.table_row).style("background-color", "rgba(0, 0, 0, 0)")
	.style("color", "black");
}

function tooltip_on(d, i) {
    var object = d3.select(this);
    var svg = d3.select(object[0][0].ownerSVGElement);
    var coordinates = d3.mouse(object[0][0].ownerSVGElement);

    var string = d;

    if (!isNaN(string)) {
	string = tooltip_format_print(d);
    }

    var container = svg.append("g")
	.attr("id", "tooltip_" + id_str_fixup(string));

    var text = container.append("text")
	.attr("class", "tooltip")
	.attr("x", coordinates[0] + 20)
	.attr("y", coordinates[1] - 20)
	.style("text-anchor", "start")
	.text(string);

    var dimensions = text[0][0].getBBox();

    var tooltip_margin = 10;

    // check if the box will flow off the right side of the chart
    // before drawing it and update the location of the text if it
    // will
    if ((dimensions.x + dimensions.width + tooltip_margin) > total_width) {
	text.attr("x", dimensions.x + (total_width - (dimensions.x + dimensions.width + tooltip_margin + 5)));

	// update the dimenions since they have changed
	dimensions = text[0][0].getBBox();
    }

    // insert the box before the text so that the text appears on top
    // of it rather than below it
    container.insert("rect", ".tooltip")
	.attr("class", "tooltip")
	.attr("x", dimensions.x - tooltip_margin)
	.attr("y", dimensions.y - tooltip_margin)
	.attr("rx", 10)
	.attr("ry", 10)
	.attr("width", dimensions.width + 2 * tooltip_margin)
	.attr("height", dimensions.height + 2 * tooltip_margin);
}

function tooltip_off(d, i) {
    var object = d3.select(this);
    var svg = d3.select(object[0][0].ownerSVGElement);

    var string = d;

    if (!isNaN(string)) {
	string = tooltip_format_print(d);
    }

    svg.select("#tooltip_" + id_str_fixup(string)).remove();
}

function set_x_axis_timeseries_label(svg, location, domain, timezone) {
    var label = "Time ";

    if (timezone == "local") {
	label += "(" + timezone_print(domain[0]) + "): " + local_time_format_print(domain[0]) + " - " + local_time_format_print(domain[1]);
    } else {
	label += "(UTC/GMT): " + utc_time_format_print(domain[0]) + " - " + utc_time_format_print(domain[1]);
    }

    svg.select("#" + location + "_x_axis_label").text(label);
}
