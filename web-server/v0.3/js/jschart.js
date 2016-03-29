
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

var margin = { top: 70, right: 87, bottom: 66, left: 65 },
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
var charts = [];

// queue to use for generating charts, 1 at a time to limit the total amount of concurrency
var charts_queue = d3_queue.queue(1);

var help = "This chart provides interactive features to assist the user in interpreting the data.\n\n";
help += "You can \"lock\" a dataset to be hightlighted by clicking it's text in the legend or it's row in the table to the right of the chart.  Click either to \"unlock\" the selection.\n\n";
help += "You can show or hide all datasets using the \"Show\" or \"Hide\" buttons at the top of the chart area.  Individual datasets can be hidden or unhidden by clicking the legend icon for that dataset.\n\n";
help += "When moving your mouse around the chart area, the coordinates will be displayed in the upper right part of the chart area.\n\n";
help += "You can zoom into a selected area by clicking in the chart area and dragging the cursor to the opposite corner of the rectangular area you would like to focus on.  When you release the cursor the selection will be zoomed.\n\n";
help += "You can also zoom in/out using the +/- controls which are visible when the mouse is over the chart area.\n\n";
help += "You can control the panning and/or zooming using the slider controls above and to the right of the chart area.\n\n";
help += "You can apply any x-axis zooming to all charts on the page by clicking the \"Apply X-Axis Zoom to All\" button (as long as the x-axis domains match).\n\n";
help += "To reset the chart area to it's original state after being panned/zoomed, hit the \"Reset Zoom/Pan\" button in the upper right.\n\n";
help += "You can download a CSV file for the data by clicking the \"Export Data as CSV\" button located under the chart title.  The exported data is limited by x-axis zooming, if performed.\n\n";
help += "When the page has completed generating all charts, the background will change colors to signal that loading is complete.\n";

function dataset(index, name, mean, median, values) {
    this.index = index;
    this.name = name;
    this.mean = mean;
    this.median = median;
    this.highlighted = false;
    this.hidden = false;
    this.histogram = { samples: 0,
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
    this.dom = { table: { row: null,
			  mean: null,
			  median: null,
			  samples: null,
			  stacked: { mean: null,
				     median: null
				   },
			  histogram: { min: null,
				       max: null,
				       p90: null,
				       p95: null,
				       p99: null,
				       p9999: null
				     }
			},
		 path: null,
		 points: null,
		 legend: { rect: null,
			   label: null
			 }
	       };
    this.values = [];
}

function chart(title, stacked, data_model, x_axis_title, y_axis_title, location, options) {
    this.chart_title = title;
    this.stacked = stacked;
    this.data_model = data_model;
    this.location = location;
    this.legend_columns = legend_properties.columns;
    this.dataset_count = 0;

    this.x = { scale: { chart: null,
			zoom: null
		      },
	       brush: null,
	       axis: { title: { text: x_axis_title,
				dom: null
			      },
		       chart: null,
		       zoom: null
		     },
	       slider: null
	     };

    this.y = { scale: { chart: null,
			zoom: null
		      },
	       brush: null,
	       axis: { title: { text: y_axis_title,
				dom: null
			      },
		       chart: null,
		       zoom: null
		     },
	       slider: null
	     };

    this.chart = { svg: null,
		   container: null,
		   show_all: null,
		   hide_all: null,
		   selection: null,
		   loading: null,
		   legend: null,
		   plot: null,
		   group: null,
		   points: null,
		   zoomout: null,
		   zoomin: null,
		   xcursorline: null,
		   ycursorline: null,
		   coordinates: null,
		   playpause: null,
		   axis: { x: { chart: null,
				zoom: null
			      },
			   y: { chart: null,
				zoom: null
			      }
			 }
		 };

    this.dom = { div: null,
		 table: { location: null,
			  table: null,
			  stacked: { median: null,
				     mean: null
				   }
			}
	       };

    this.table = { stacked_mean: 0,
		   valid_stacked_mean: 0,
		   stacked_median: 0
		 };

    this.state = { user_x_zoomed: false,
		   user_y_zoomed: false,
		   chart_selection: -1,
		   selection_start: null,
		   selection_stop: null,
		   selection_active: false,
		   live_update: true
		 };

    this.functions = { area: null,
		       stack: null,
		       line: null
		     };

    this.datasets_queue = null;
    this.datasets = [];

    this.options = { timezone: null,
		     legend_entries: null,
		     packed: 0,
		     plotfiles: null,
		     csvfiles: null,
		     plotfile: null,
		     plotfiles: null,
		     json_plotfile: null,
		     json_args: null,
		     raw_data_source: [],
		     update_interval: null,
		     history_length: null,
		     x: { min: null,
			  max: null,
			  scale: { linear: true,
				   log: false,
				   time: false
				 }
			},
		     y: { min: null,
			  max: null,
			  scale: { linear: true,
				   log: false
				 }
			},
		   };

    this.interval = null;

    // option(s) "parsing"
    if (this.data_model == "timeseries") {
	this.options.x.scale.time = true;
	this.options.x.scale.linear = false;
    } else {
	if ((options.x_log_scale !== undefined) &&
	    options.x_log_scale) {
	    this.options.x.scale.log = true;
	    this.options.x.scale.linear = false;
	}
    }

    if ((options.y_log_scale !== undefined) &&
	options.y_log_scale) {
	this.options.y.scale.log = true;
	this.options.y.scale.linear = false;
    }

    if (options.timeseries_timezone !== undefined) {
	this.options.timezone = options.timeseries_timezone;
    }

    if (options.legend_entries !== undefined) {
	this.options.legend_entries = options.legend_entries;
    } else {
	this.options.legend_entries = [];
    }

    if (options.packed !== undefined) {
	this.options.packed = options.packed;
	this.dataset_count = this.options.packed;
    } else if (options.plotfiles !== undefined) {
	this.options.plotfiles = options.plotfiles;
	this.dataset_count = this.options.plotfiles.length;
    }

    if (options.csvfiles !== undefined) {
	this.options.csvfiles = options.csvfiles;
    }

    if (options.plotfile !== undefined) {
	this.options.plotfile = options.plotfile;
    }

    if (options.plotfiles !== undefined) {
	this.options.plotfiles = options.plotfiles;
    }

    if (options.json_plotfile !== undefined) {
	this.options.json_plotfile = options.json_plotfile;
    }

    if (options.json_args !== undefined) {
	this.options.json_args = options.json_args;
    }

    if (options.raw_data_sources !== undefined) {
	this.options.raw_data_sources = options.raw_data_sources;
    } else {
	this.options.raw_data_sources = [];
    }

    if (options.update_interval !== undefined) {
	this.options.update_interval = options.update_interval;
    }

    if (options.history_length !== undefined) {
	this.options.history_length = options.history_length;
    }

    if (options.x_min !== undefined) {
	this.options.x.min = options.x_min;
    }

    if (options.x_max !== undefined) {
	this.options.x.max = options.x_max;
    }

    if (options.y_min !== undefined) {
	this.options.y.min = options.y_min;
    }

    if (options.y_max !== undefined) {
	this.options.y.max = options.y_max;
    }
}

function compute_stacked_median(charts_index) {
    var foo = [];
    var bar = [];

    charts[charts_index].datasets.map(function(d) {
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

function parse_plot_file(charts_index, datasets_index, text) {
    charts[charts_index].datasets[datasets_index] = new dataset(datasets_index, "", "No Samples", "No Samples", []);

    dsv.parseRows(text).map(function(row) {
	var index = row[0].indexOf("#LABEL:");

	if (index == -1) {
	    if (charts[charts_index].data_model == "histogram") {
		charts[charts_index].datasets[datasets_index].histogram.samples += +row[1];
		charts[charts_index].datasets[datasets_index].histogram.sum += (+row[0] * +row[1]);
	    }
	    charts[charts_index].datasets[datasets_index].values.push({ x: +row[0], y: +row[1] });
	} else {
	    var tmp = row[0].substring(7);
	    row.shift();
	    row.map(function(d) {
		tmp = tmp + " " + d;
	    });

	    charts[charts_index].datasets[datasets_index].name = tmp;
	}
    });

    if (charts[charts_index].datasets[datasets_index].values.length > 0) {
	charts[charts_index].datasets[datasets_index].mean = d3.mean(charts[charts_index].datasets[datasets_index].values, function(d) { return d.y; });
	charts[charts_index].datasets[datasets_index].median = d3.median(charts[charts_index].datasets[datasets_index].values, function(d) { return d.y; });

	if (charts[charts_index].data_model == "histogram") {
	    charts[charts_index].datasets[datasets_index].histogram.mean = charts[charts_index].datasets[datasets_index].histogram.sum / charts[charts_index].datasets[datasets_index].histogram.samples;
	    charts[charts_index].datasets[datasets_index].histogram.min = charts[charts_index].datasets[datasets_index].values[0].x;
	    charts[charts_index].datasets[datasets_index].histogram.max = charts[charts_index].datasets[datasets_index].values[charts[charts_index].datasets[datasets_index].values.length - 1].x;

	    var count = 0;
	    var threshold = charts[charts_index].datasets[datasets_index].histogram.samples * 0.5;
	    var threshold_p90 = charts[charts_index].datasets[datasets_index].histogram.samples * 0.9;
	    var threshold_p95 = charts[charts_index].datasets[datasets_index].histogram.samples * 0.95;
	    var threshold_p99 = charts[charts_index].datasets[datasets_index].histogram.samples * 0.99;
	    var threshold_p9999 = charts[charts_index].datasets[datasets_index].histogram.samples * 0.9999;
	    for (var i=0; i < charts[charts_index].datasets[datasets_index].values.length; i++) {
		count += charts[charts_index].datasets[datasets_index].values[i].y;
		if ((charts[charts_index].datasets[datasets_index].histogram.median === null) && (count >= threshold)) {
		    charts[charts_index].datasets[datasets_index].histogram.median = charts[charts_index].datasets[datasets_index].values[i].x;
		}
		if ((charts[charts_index].datasets[datasets_index].histogram.p90 === null) && (count >= threshold_p90)) {
		    charts[charts_index].datasets[datasets_index].histogram.p90 = charts[charts_index].datasets[datasets_index].values[i].x;
		}
		if ((charts[charts_index].datasets[datasets_index].histogram.p95 === null) && (count >= threshold_p95)) {
		    charts[charts_index].datasets[datasets_index].histogram.p95 = charts[charts_index].datasets[datasets_index].values[i].x;
		}
		if ((charts[charts_index].datasets[datasets_index].histogram.p99 === null) && (count >= threshold_p99)) {
		    charts[charts_index].datasets[datasets_index].histogram.p99 = charts[charts_index].datasets[datasets_index].values[i].x;
		}
		if ((charts[charts_index].datasets[datasets_index].histogram.p9999 === null) && (count >= threshold_p9999)) {
		    charts[charts_index].datasets[datasets_index].histogram.p9999 = charts[charts_index].datasets[datasets_index].values[i].x;
		}
	    }
	}
    } else {
	charts[charts_index].datasets[datasets_index].mean = "No Samples";
	charts[charts_index].datasets[datasets_index].median = "No Samples";

	if (charts[charts_index].data_model == "histogram") {
	    charts[charts_index].datasets[datasets_index].histogram.mean = "No Samples";
	    charts[charts_index].datasets[datasets_index].histogram.median = "No Samples";
	    charts[charts_index].datasets[datasets_index].histogram.min = "No Samples";
	    charts[charts_index].datasets[datasets_index].histogram.max = "No Samples";
	    charts[charts_index].datasets[datasets_index].histogram.p90 = "No Samples";
	    charts[charts_index].datasets[datasets_index].histogram.p95 = "No Samples";
	    charts[charts_index].datasets[datasets_index].histogram.p99 = "No Samples";
	    charts[charts_index].datasets[datasets_index].histogram.p9999 = "No Samples";
	}
    }
}

function update_chart(charts_index) {
    var last_timestamp = 0;
    if (charts[charts_index].datasets.length) {
	last_timestamp = charts[charts_index].datasets[0].last_timestamp;
    }

    var post_data = "time=" + last_timestamp;

    if (charts[charts_index].options.json_args) {
	post_data += "&" + charts[charts_index].options.json_args;
    }

    d3.json(charts[charts_index].options.json_plotfile)
	.header("Content-Type", "application/x-www-form-urlencoded")
	.post(post_data, function(error, json) {
	    if ((json !== undefined) &&
		(json.data_series_names !== undefined) &&
		(json.x_axis_series !== undefined) &&
		(json.data !== undefined)) {
		var timebase = new Date().getTime() / 1000;

		var table = d3.select(charts[charts_index].table.table);

		charts[charts_index].table.stacked_mean = 0;
		charts[charts_index].table.valid_stacked_mean = 0;

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
			charts[charts_index].datasets[dataset_index].values.push({ timestamp: d[0], x: 0, y: d[index] });
			charts[charts_index].datasets[dataset_index].last_timestamp = d[0];
		    });

		    if (charts[charts_index].options.history_length) {
			var length = charts[charts_index].datasets[dataset_index].values.length;

			if (length > charts[charts_index].options.history_length) {
			    charts[charts_index].datasets[dataset_index].values.splice(0, length - charts[charts_index].options.history_length);
			}
		    }

		    charts[charts_index].datasets[dataset_index].values.map(function(d) {
			d.x = d.timestamp - timebase;
		    });

		    var mean;
		    var median;

		    if (charts[charts_index].datasets[dataset_index].values.length > 0) {
			mean = d3.mean(charts[charts_index].datasets[dataset_index].values, function(d) { return d.y; });
			median = d3.median(charts[charts_index].datasets[dataset_index].values, function(d) { return d.y });

			charts[charts_index].table.stacked_mean += mean;
			charts[charts_index].table.valid_stacked_mean = 1;
		    } else {
			mean = "No Samples";
			median = "No Samples"
		    }

		    charts[charts_index].datasets[dataset_index].mean = mean;
		    charts[charts_index].datasets[dataset_index].median = median;

		    charts[charts_index].datasets[dataset_index].dom.table.mean.text(table_format_print(mean));
		    charts[charts_index].datasets[dataset_index].dom.table.median.text(table_format_print(median));
		    charts[charts_index].datasets[dataset_index].dom.table.samples.text(charts[charts_index].datasets[dataset_index].values.length);

		    dataset_index++;
		}

		if (charts[charts_index].stacked) {
		    if (charts[charts_index].table.valid_stacked_mean) {
			charts[charts_index].table.stacked_mean = table_format_print(charts[charts_index].table.stacked_mean);
		    } else {
			charts[charts_index].table.stacked_mean = "No Samples";
		    }
		    charts[charts_index].dom.table.stacked.mean.text(charts[charts_index].table.stacked_mean);

		    charts[charts_index].table.stacked_median = compute_stacked_median(charts_index);
		    if (isFinite(charts[charts_index].table.stacked_median)) {
			charts[charts_index].table.stacked_median = table_format_print(charts[charts_index].table.stacked_median);
		    }
		    charts[charts_index].dom.table.stacked.median.text(charts[charts_index].table.stacked_median);

		    charts[charts_index].datasets = charts[charts_index].functions.stack(charts[charts_index].datasets);
		}

		charts[charts_index].x.scale.chart.domain([
		    d3.min(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.x; }); }),
		    d3.max(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.x; }); })
		]);

		if (charts[charts_index].stacked) {
		    charts[charts_index].y.scale.chart.domain([
			d3.min(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y0; }); }),
			d3.max(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y0 + v.y; }); })
		    ]);
		} else {
		    charts[charts_index].y.scale.chart.domain([
			d3.min(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y; }); }),
			d3.max(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y; }); })
		    ]);
		}

		var domain = charts[charts_index].x.scale.chart.domain();

		if (charts[charts_index].options.x.min) {
		    domain[0] = charts[charts_index].options.x.min;
		}

		if (charts[charts_index].options.x.max) {
		    domain[1] = charts[charts_index].options.x.max;
		}

		charts[charts_index].x.scale.chart.domain(domain);
		charts[charts_index].x.scale.zoom.domain(charts[charts_index].x.scale.chart.domain());

		if (! charts[charts_index].state.user_x_zoomed) {
		    charts[charts_index].x.brush.extent(domain);
		}

		var domain = charts[charts_index].y.scale.chart.domain();

		if (charts[charts_index].options.y.min) {
		    domain[0] = charts[charts_index].options.y.min;
		}

		if (charts[charts_index].options.y.max) {
		    domain[1] = charts[charts_index].options.y.max;
		}

		charts[charts_index].y.scale.chart.domain(domain);
		charts[charts_index].y.scale.zoom.domain(charts[charts_index].y.scale.chart.domain());

		if (! charts[charts_index].state.user_y_zoomed) {
		    charts[charts_index].y.brush.extent(domain);
		}

		zoom_it(charts_index, 0);
	    }
	});
}

function load_json(charts_index, callback) {
    var post_data = "";

    if (charts[charts_index].options.json_args) {
	post_data += charts[charts_index].options.json_args;
    }

    d3.json(charts[charts_index].options.json_plotfile)
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

		    charts[charts_index].datasets[dataset_index] = new dataset(index-1, json.data_series_names[index], 0, 0, []);

		    json.data.map(function(d) {
			charts[charts_index].datasets[dataset_index].values.push({ timestamp: d[x_axis_index], x: d[x_axis_index] - timebase, y: d[index] });
			charts[charts_index].datasets[dataset_index].last_timestamp = d[x_axis_index];
		    });

		    if (charts[charts_index].datasets[dataset_index].values.length > 0) {
			charts[charts_index].datasets[dataset_index].mean = d3.mean(charts[charts_index].datasets[dataset_index].values, function(d) { return d.y; });
			charts[charts_index].datasets[dataset_index].median = d3.median(charts[charts_index].datasets[dataset_index].values, function(d) { return d.y; });
		    } else {
			charts[charts_index].datasets[dataset_index].mean = "No Samples";
			charts[charts_index].datasets[dataset_index].median = "No Samples";
		    }

		    dataset_index++;
		}
	    }

	    // signal that we are finished asynchronously loading the data
	    callback();
	});
}

function load_csv_files(url, charts_index, callback) {
    // the call to d3.text is performed asynchronously...queue.js
    // processing is used to ensure all files are loaded prior to
    // populating the graph, avoiding parallelism issues
    d3.text(url, "text/plain")
	.get(function(error, text) {
		var index_base = charts[charts_index].datasets.length;

		if ((text === undefined) ||
		    (error !== null)) {
		    console.log("Error %O loading %s", error, url);

		    // create an error object with minimal properties
		    charts[charts_index].datasets[index_base - 1] = new dataset(index_base - 1, "Error loading " + url, "No Samples", "No Samples", []);

		    // signal that we are finished asynchronously failing to load the data
		    callback();
		    return;
		}

		var sample_counter = 0;

		var data = d3.csv.parseRows(text).map(function(row) {
		    if (sample_counter == 0) {
			for (var i=1; i<row.length; i++) {
			    charts[charts_index].datasets[index_base + i - 1] = new dataset(index_base + i - 1, row[i], "No Samples", "No Samples", []);
			}
		    } else {
			for (var i=1; i<row.length; i++) {
			    if (row[i] == "") {
				continue;
			    }

			    charts[charts_index].datasets[index_base + i - 1].values.push({ x: +row[0], y: +row[i] });

			    if (charts[charts_index].data_model == "histogram") {
				charts[charts_index].datasets[index_base + i -1].histogram.samples += +row[i];
				charts[charts_index].datasets[index_base + i -1].histogram.sum += (+row[0] * +row[i]);
			    }
			}
		    }

		    sample_counter++;
		});

		for (var i=index_base; i<charts[charts_index].datasets.length; i++) {
		    if (charts[charts_index].datasets[i].values.length) {
			charts[charts_index].datasets[i].mean = d3.mean(charts[charts_index].datasets[i].values, function(d) { return d.y; });
			charts[charts_index].datasets[i].median = d3.median(charts[charts_index].datasets[i].values, function(d) { return d.y });

			if (charts[charts_index].data_model == "histogram") {
			    charts[charts_index].datasets[i].histogram.mean = charts[charts_index].datasets[i].histogram.sum / charts[charts_index].datasets[i].histogram.samples;
			    charts[charts_index].datasets[i].histogram.min = charts[charts_index].datasets[i].values[0].x;
			    charts[charts_index].datasets[i].histogram.max = charts[charts_index].datasets[i].values[charts[charts_index].datasets[i].values.length - 1].x;

			    var count = 0;
			    var threshold = charts[charts_index].datasets[i].histogram.samples * 0.5;
			    var threshold_p90 = charts[charts_index].datasets[i].histogram.samples * 0.9;
			    var threshold_p95 = charts[charts_index].datasets[i].histogram.samples * 0.95;
			    var threshold_p99 = charts[charts_index].datasets[i].histogram.samples * 0.99;
			    var threshold_p9999 = charts[charts_index].datasets[i].histogram.samples * 0.9999;
			    for (var p=0; p < charts[charts_index].datasets[i].values.length; p++) {
				count += charts[charts_index].datasets[i].values[p].y;
				if ((charts[charts_index].datasets[i].histogram.median === null) && (count >= threshold)) {
				    charts[charts_index].datasets[i].histogram.median = charts[charts_index].datasets[i].values[p].x;
				}
				if ((charts[charts_index].datasets[i].histogram.p90 === null) && (count >= threshold_p90)) {
				    charts[charts_index].datasets[i].histogram.p90 = charts[charts_index].datasets[i].values[p].x;
				}
				if ((charts[charts_index].datasets[i].histogram.p95 === null) && (count >= threshold_p95)) {
				    charts[charts_index].datasets[i].histogram.p95 = charts[charts_index].datasets[i].values[p].x;
				}
				if ((charts[charts_index].datasets[i].histogram.p99 === null) && (count >= threshold_p99)) {
				    charts[charts_index].datasets[i].histogram.p99 = charts[charts_index].datasets[i].values[p].x;
				}
				if ((charts[charts_index].datasets[i].histogram.p9999 === null) && (count >= threshold_p9999)) {
				    charts[charts_index].datasets[i].histogram.p9999 = charts[charts_index].datasets[i].values[p].x;
				}
			    }
			}
		    }
		}

		// signal that we are finished asynchronously loading the data
		callback();
	    });
}

function load_plot_file(url, charts_index, callback) {
    load_plot_files(url, charts_index, -1, callback)
}

function load_plot_files(url, charts_index, index, callback) {
    // the call to d3.text is performed asynchronously...queue.js
    // processing is used to ensure all files are loaded prior to
    // populating the graph, avoiding parallelism issues
    d3.text(url, "text/plain")
	.get(function(error, text) {
		if ((text === undefined) ||
		    (error !== null)) {
		    console.log("Error %O loading %s", error, url);

		    // create an error object with minimal properties
		    charts[charts_index].datasets[index] = new dataset(index, "Error loading " + url, "No Samples", "No Samples", []);

		    // signal that we are finished asynchronously failing to load the data
		    callback();
		    return;
		}

		var packed_separator = "--- JSChart Packed Plot File V1 ---";
		var packed_index = text.indexOf(packed_separator);
		var prev_packed_index = packed_index;
		if ((packed_index == -1) && (index >= 0)) {
		    parse_plot_file(charts_index, index, text);
		} else {
		    var dataset_index = 0;

		    while (packed_index >= 0) {
			prev_packed_index = packed_index;
			packed_index = text.indexOf(packed_separator, packed_index+1);

			parse_plot_file(charts_index, dataset_index++, text.slice(prev_packed_index + packed_separator.length + 1, packed_index));
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

function complete_chart(charts_index) {
    charts[charts_index].x.scale.chart.domain([
	      d3.min(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.x; }); }),
	      d3.max(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.x; }); })
	      ]);

    var domain = charts[charts_index].x.scale.chart.domain();

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

    if (charts[charts_index].options.x.min) {
	domain[0] = charts[charts_index].options.x.min;
    }

    if (charts[charts_index].options.x.max) {
	domain[1] = charts[charts_index].options.x.max;
    }

    charts[charts_index].x.scale.chart.domain(domain);
    charts[charts_index].x.scale.zoom.domain(charts[charts_index].x.scale.chart.domain());

    if (charts[charts_index].datasets.length < charts[charts_index].legend_columns) {
	charts[charts_index].legend_columns = charts[charts_index].datasets.length;
    }

    charts[charts_index].chart.legend = charts[charts_index].chart.container.selectAll(".legend")
        .data(charts[charts_index].datasets)
	.enter().append("g")
        .attr("class", "legend")
        .attr("transform", function(d, i) { return "translate(" + (-margin.left + 5 + (i % charts[charts_index].legend_columns) * (total_width / charts[charts_index].legend_columns)) + "," + (height + legend_properties.margin.top + (Math.floor(i / charts[charts_index].legend_columns) * legend_properties.row_height)) + ")"; });

    charts[charts_index].chart.legend.append("rect")
	.attr("class", function(d) { d.dom.legend.rect = d3.select(this); return "legendrect"; })
	.attr("onclick", function(d) { return "toggle_hide(" + charts_index + ", " + d.index + ")"; })
	.attr("onmouseover", function(d) { return "mouseover_highlight_function(" + charts_index + ", " + d.index + ")"; })
	.attr("onmouseout", function(d) { return "mouseout_highlight_function(" + charts_index + ", " + d.index + ")"; })
	.attr("width", 16)
	.attr("height", 16)
	.style("outline-color", function(d) { return mycolors(d.index); } )
	.style("fill", function(d) { return mycolors(d.index); } );

    var legend_label_offset = 25;

    charts[charts_index].chart.legend.append("text")
	.attr("class", function(d) { d.dom.legend.label = d3.select(this); return "legendlabel"; })
	.attr("onclick", function(d) { return "click_highlight_function(" + charts_index + ", " + d.index + ")"; })
	.attr("onmouseover", function(d) { return "mouseover_highlight_function(" + charts_index + ", " + d.index + ")"; })
	.attr("onmouseout", function(d) { return "mouseout_highlight_function(" + charts_index + ", " + d.index + ")"; })
	.attr("x", legend_label_offset)
	.attr("y", 13.5)
	.text(function(d) { return d.name; });

    charts[charts_index].chart.container.selectAll(".legendlabel")
	.each(function(d, i) {
		var label_width = this.getBBox().width;

		if (label_width >= (total_width / charts[charts_index].legend_columns - legend_label_offset)) {
		    var label = d3.select(this);

		    label.text(d.name.substr(0, 21) + '...')
			.on("mouseover", tooltip_on)
			.on("mouseout", tooltip_off);
		}
	    });

    if (charts[charts_index].options.legend_entries) {
	var legend_entries = charts[charts_index].chart.container.selectAll(".legendentries")
	    .data(charts[charts_index].options.legend_entries)
	    .enter().append("g")
	    .attr("class", "legend")
	    .attr("transform", function(d, i) { return "translate(" + (-margin.left + 5) + ", " + (height + legend_properties.margin.top + ((Math.floor(charts[charts_index].datasets.length / charts[charts_index].legend_columns) + i) * legend_properties.row_height)) + ")"; });

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

	for(var i=0; i<charts[charts_index].datasets.length; i++) {
	    if (charts[charts_index].datasets[i].values.length == 0) {
		charts[charts_index].datasets.splice(i, 1);
		loop = 1;
		errors++;
		break;
	    }
	}
    }

    if (charts[charts_index].stacked) {
	charts[charts_index].datasets = charts[charts_index].functions.stack(charts[charts_index].datasets);

	charts[charts_index].y.scale.chart.domain([
		  d3.min(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y0; }); }),
		  d3.max(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y0 + v.y; }); })
		  ]);
    } else {
	charts[charts_index].y.scale.chart.domain([
		  d3.min(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.min(c.values, function(v) { return v.y; }); }),
		  d3.max(charts[charts_index].datasets, function(c) { if (c.values === undefined) { return null; } return d3.max(c.values, function(v) { return v.y; }); })
		  ]);
    }

    var domain = charts[charts_index].y.scale.chart.domain();

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

    if (!charts[charts_index].stacked &&
	!charts[charts_index].options.y.scale.log &&
	(domain[0] > 0)) {
	domain[0] = 0;
    }

    domain[1] *= 1.05;

    if (charts[charts_index].options.y.min) {
	domain[0] = charts[charts_index].options.y.min;
    }

    if (charts[charts_index].options.y.max) {
	domain[1] = charts[charts_index].options.y.max;
    }

    charts[charts_index].y.scale.chart.domain(domain);
    charts[charts_index].y.scale.zoom.domain(charts[charts_index].y.scale.chart.domain());

    charts[charts_index].chart.axis.x.chart.call(charts[charts_index].x.axis.chart);
    charts[charts_index].chart.axis.x.zoom.call(charts[charts_index].x.axis.zoom);
    charts[charts_index].chart.axis.y.chart.call(charts[charts_index].y.axis.chart);
    charts[charts_index].chart.axis.y.zoom.call(charts[charts_index].y.axis.zoom);
    fix_y_axis_labels(charts_index);

    if (charts[charts_index].data_model == "timeseries") {
	set_x_axis_timeseries_label(charts_index);
    }

    if (charts[charts_index].stacked) {
	charts[charts_index].chart.plot = charts[charts_index].chart.container.selectAll(".plot")
	    .data(charts[charts_index].datasets)
	    .enter().append("g")
	    .attr("class", "plot");

	charts[charts_index].chart.plot.append("path")
	    .attr("class", function(d) { d.dom.path = d3.select(this); return "area"; })
	    .attr("d", function(d) { if (d.values === undefined) { return null; } return charts[charts_index].functions.area(d.values); })
	    .style("fill", function(d) { return mycolors(d.index); })
	    .attr("clip-path", "url(#clip)");

	charts[charts_index].datasets.map(function(d) {
		if (d.values.length > 1) {
		    return;
		}

		charts[charts_index].chart.group = d3.select(d.dom.path[0][0].parentNode).append("g")
		    .attr("class", "points");

		charts[charts_index].chart.group.selectAll(".points")
		    .data(d.values)
		    .enter().append("line")
		    .attr("class", function(b) { d.dom.points = d3.select(this); return "points"; })
		    .attr("r", 3)
		    .attr("clip-path", "url(#clip)")
		    .style("stroke", mycolors(d.index))
		    .attr("x1", function(b) { return charts[charts_index].x.scale.chart(b.x); })
		    .attr("x2", function(b) { return charts[charts_index].x.scale.chart(b.x); })
		    .attr("y1", function(b) { return charts[charts_index].y.scale.chart(b.y0); })
		    .attr("y2", function(b) { return charts[charts_index].y.scale.chart(b.y + b.y0); });
	    });
    } else {
	charts[charts_index].chart.plot = charts[charts_index].chart.container.selectAll(".plot")
	    .data(charts[charts_index].datasets)
	    .enter().append("g")
	    .attr("class", "plot");

	charts[charts_index].chart.plot.append("path")
	    .attr("class", function(d) { d.dom.path = d3.select(this); return "line"; })
	    .attr("d", function(d) { if (d.values === undefined) { return null; } return charts[charts_index].functions.line(d.values); })
	    .style("stroke", function(d) { return mycolors(d.index) })
	    .attr("clip-path", "url(#clip)");

	charts[charts_index].datasets.map(function(d) {
		if (d.values.length > 1) {
		    return;
		}

		charts[charts_index].chart.group = d3.select(d.dom.path[0][0].parentNode).append("g")
		    .attr("class", "points");

		charts[charts_index].chart.group.selectAll(".points")
		    .data(d.values)
		    .enter().append("circle")
		    .attr("class", function(b) { d.dom.points = d3.select(this); return "points"; })
		    .attr("r", 3)
		    .attr("clip-path", "url(#clip)")
		    .style("fill", mycolors(d.index))
		    .style("stroke", mycolors(d.index))
		    .attr("cx", function(b) { return charts[charts_index].x.scale.chart(b.x); })
		    .attr("cy", function(b) { return charts[charts_index].y.scale.chart(b.y); });
	    });
    }

    return errors;
}

function create_table_controls(charts_index) {
    var colspan = 4;

    var table_header = d3.select(charts[charts_index].table.table).select("tr").select("th");

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
    if (charts[charts_index].options.history_length) {
	textbox.value = charts[charts_index].options.history_length;
    }

    cell.appendChild(textbox);

    var button = document.createElement("button")
    button.innerHTML = "Update";
    button.onclick = function() {
	var value = d3.select("#" + location + "_history_length")[0][0].value;
	if (!isNaN(value)) {
	    charts[charts_index].options.history_length = value;
	} else if (charts[charts_index].options.history_length) {
	    d3.select("#" + location + "_history_length")[0][0].value = charts[charts_index].options.history_length;
	}
    };

    cell.appendChild(button);

    row.appendChild(cell);

    charts[charts_index].table.table.appendChild(row);

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
    if (charts[charts_index].options.update_interval) {
	textbox.value = charts[charts_index].options.update_interval;
    }

    cell.appendChild(textbox);

    var button = document.createElement("button")
    button.innerHTML = "Update";
    button.onclick = function() {
	var value = d3.select("#" + location + "_update_interval")[0][0].value;
	if (!isNaN(value)) {
	    charts[charts_index].options.update_interval = value;
	    charts[charts_index].chart.container.select("#playpause")[0][0].__onclick();
	    charts[charts_index].chart.container.select("#playpause")[0][0].__onclick();
	} else {
	    if (charts[charts_index].options.update_interval) {
		d3.select("#" + location + "_update_interval")[0][0].value = charts[charts_index].options.update_interval;
	    }
	}
    };

    cell.appendChild(button);

    row.appendChild(cell);

    charts[charts_index].table.table.appendChild(row);
}

function create_table_entries(charts_index) {
    var colspan;

    if (charts[charts_index].data_model == "histogram") {
	colspan = 10;
    } else {
	colspan = 4;
    }

    charts[charts_index].table.table = document.createElement("table");
    charts[charts_index].table.table.className = 'chart';

    var table_header_1 = document.createElement("tr");
    table_header_1.className = 'header';

    var table_header_1_cell = document.createElement("th");
    table_header_1_cell.colSpan = colspan;
    table_header_1_cell.innerHTML = charts[charts_index].chart_title;

    table_header_1.appendChild(table_header_1_cell);
    charts[charts_index].table.table.appendChild(table_header_1);

    if (charts[charts_index].data_model == "histogram") {
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

	charts[charts_index].table.table.appendChild(table_header_2);

	charts[charts_index].dom.table.location.appendChild(charts[charts_index].table.table);
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

	charts[charts_index].table.table.appendChild(table_header_2);

	charts[charts_index].dom.table.location.appendChild(charts[charts_index].table.table);
    }

    charts[charts_index].datasets.map(function(d) {
	    d.dom.table.row = document.createElement("tr");
	    d.dom.table.row.onclick = function() { click_highlight_function(charts_index, d.index); };
	    d.dom.table.row.onmouseover = function() { mouseover_highlight_function(charts_index, d.index); };
	    d.dom.table.row.onmouseout = function() { mouseout_highlight_function(charts_index, d.index); };

	    var name_cell = document.createElement("td");
	    name_cell.align = "left";
	    name_cell.innerHTML = d.name;
	    d.dom.table.row.appendChild(name_cell);

	    d.dom.table.mean = document.createElement("td");
	    d.dom.table.mean.align = "right";
	    if (charts[charts_index].data_model == "histogram") {
		if (isFinite(d.histogram.mean)) {
		    d.dom.table.mean.innerHTML = table_format_print(d.histogram.mean);
		} else {
		    d.dom.table.mean.innerHTML = d.histogram.mean;
		}
	    } else {
		if (isFinite(d.mean)) {
		    d.dom.table.mean.innerHTML = table_format_print(d.mean);
		} else {
		    d.dom.table.mean.innerHTML = d.mean;
		}
		if (charts[charts_index].stacked && (d.mean !== undefined) && isFinite(d.mean)) {
		    charts[charts_index].table.valid_stacked_mean = 1;
		    charts[charts_index].table.stacked_mean += d.mean;
		}
	    }
	    d.dom.table.row.appendChild(d.dom.table.mean);
	    d.dom.table.mean = d3.select(d.dom.table.mean);

	    d.dom.table.median = document.createElement("td");
	    d.dom.table.median.align = "right";
	    if (charts[charts_index].data_model == "histogram") {
		if (isFinite(d.histogram.median)) {
		    d.dom.table.median.innerHTML = table_format_print(d.histogram.median);
		} else {
		    d.dom.table.median.innerHTML = d.histogram.median;
		}
	    } else {
		if (isFinite(d.median)) {
		    d.dom.table.median.innerHTML = table_format_print(d.median);
		} else {
		    d.dom.table.median.innerHTML = d.median;
		}
	    }
	    d.dom.table.row.appendChild(d.dom.table.median);
	    d.dom.table.median = d3.select(d.dom.table.median);

	    if (charts[charts_index].data_model == "histogram") {
		d.dom.table.histogram.min = document.createElement("td");
		d.dom.table.histogram.min.align = "right";
		if (isFinite(d.histogram.min)) {
		    d.dom.table.histogram.min.innerHTML = table_format_print(d.histogram.min);
		} else {
		    d.dom.table.histogram.min.innerHTML = d.histogram.min;
		}
		d.dom.table.row.appendChild(d.dom.table.histogram.min);
		d.dom.table.histogram.min = d3.select(d.dom.table.histogram.min);

		d.dom.table.histogram.max = document.createElement("td");
		d.dom.table.histogram.max.align = "right";
		if (isFinite(d.histogram.max)) {
		    d.dom.table.histogram.max.innerHTML = table_format_print(d.histogram.max);
		} else {
		    d.dom.table.histogram.max.innerHTML = d.histogram.max;
		}
		d.dom.table.row.appendChild(d.dom.table.histogram.max);
		d.dom.table.histogram.max = d3.select(d.dom.table.histogram.max);

		d.dom.table.histogram.p90 = document.createElement("td");
		d.dom.table.histogram.p90.align = "right";
		if (isFinite(d.histogram.p90)) {
		    d.dom.table.histogram.p90.innerHTML = table_format_print(d.histogram.p90);
		} else {
		    d.dom.table.histogram.p90.innerHTML = d.histogram.p90;
		}
		d.dom.table.row.appendChild(d.dom.table.histogram.p90);
		d.dom.table.histogram.p90 = d3.select(d.dom.table.histogram.p90);

		d.dom.table.histogram.p95 = document.createElement("td");
		d.dom.table.histogram.p95.align = "right";
		if (isFinite(d.histogram.p95)) {
		    d.dom.table.histogram.p95.innerHTML = table_format_print(d.histogram.p95);
		} else {
		    d.dom.table.histogram.p95.innerHTML = d.histogram.p95;
		}
		d.dom.table.row.appendChild(d.dom.table.histogram.p95);
		d.dom.table.histogram.p95 = d3.select(d.dom.table.histogram.p95);

		d.dom.table.histogram.p99 = document.createElement("td");
		d.dom.table.histogram.p99.align = "right";
		if (isFinite(d.histogram.p99)) {
		    d.dom.table.histogram.p99.innerHTML = table_format_print(d.histogram.p99);
		} else {
		    d.dom.table.histogram.p99.innerHTML = d.histogram.p99;
		}
		d.dom.table.row.appendChild(d.dom.table.histogram.p99);
		d.dom.table.histogram.p99 = d3.select(d.dom.table.histogram.p99);

		d.dom.table.histogram.p9999 = document.createElement("td");
		d.dom.table.histogram.p9999.align = "right";
		if (isFinite(d.histogram.p9999)) {
		    d.dom.table.histogram.p9999.innerHTML = table_format_print(d.histogram.p9999);
		} else {
		    d.dom.table.histogram.p9999.innerHTML = d.histogram.p9999;
		}
		d.dom.table.row.appendChild(d.dom.table.histogram.p9999);
		d.dom.table.histogram.p9999 = d3.select(d.dom.table.histogram.p9999);
	    }

	    d.dom.table.samples = document.createElement("td");
	    d.dom.table.samples.align = "right";
	    if (charts[charts_index].data_model == "histogram") {
		d.dom.table.samples.innerHTML = table_format_print(d.histogram.samples);
	    } else {
		d.dom.table.samples.innerHTML = table_format_print(d.values.length);
	    }
	    d.dom.table.row.appendChild(d.dom.table.samples);
	    d.dom.table.samples = d3.select(d.dom.table.samples);

	    charts[charts_index].table.table.appendChild(d.dom.table.row);

	    d.dom.table.row = d3.select(d.dom.table.row);
	});

    if (charts[charts_index].stacked) {
	var mean_row = document.createElement("tr");
	mean_row.className = "footer";

	var name_cell = document.createElement("th");
	name_cell.align = "left";
	name_cell.innerHTML = "Combined Average";
	mean_row.appendChild(name_cell);

	charts[charts_index].dom.table.stacked.mean = document.createElement("td");
	charts[charts_index].dom.table.stacked.mean.align = "right";
	if (charts[charts_index].table.valid_stacked_mean) {
	    charts[charts_index].dom.table.stacked.mean.innerHTML = table_format_print(charts[charts_index].table.stacked_mean);
	} else {
	    charts[charts_index].dom.table.stacked.mean.innerHTML = "No Samples";
	}
	mean_row.appendChild(charts[charts_index].dom.table.stacked.mean);
	charts[charts_index].dom.table.stacked.mean = d3.select(charts[charts_index].dom.table.stacked.mean);

	var blank_cell = document.createElement("td");
	blank_cell.innerHTML = "&nbsp;";
	mean_row.appendChild(blank_cell);

	if (colspan === 4) {
	    var blank_cell = document.createElement("td");
	    blank_cell.innerHTML = "&nbsp;";
	    mean_row.appendChild(blank_cell);
	}

	charts[charts_index].table.table.appendChild(mean_row);

	var median_row = document.createElement("tr");
	median_row.className = "footer";

	var name_cell = document.createElement("th");
	name_cell.align = "left";
	name_cell.innerHTML = "Combined Median";
	median_row.appendChild(name_cell);

	var blank_cell = document.createElement("td");
	blank_cell.innerHTML = "&nbsp;";
	median_row.appendChild(blank_cell);

	charts[charts_index].dom.table.stacked.median = document.createElement("td");
	charts[charts_index].dom.table.stacked.median.align = "right";
	charts[charts_index].table.stacked_median = compute_stacked_median(charts_index);
	if (isFinite(charts[charts_index].table.stacked_median)) {
	    charts[charts_index].dom.table.stacked.median.innerHTML = table_format_print(charts[charts_index].table.stacked_median);
	} else {
	    charts[charts_index].dom.table.stacked.median.innerHTML = charts[charts_index].table.stacked_median;
	}
	median_row.appendChild(charts[charts_index].dom.table.stacked.median);
	charts[charts_index].dom.table.stacked.median = d3.select(charts[charts_index].dom.table.stacked.median);

	if (colspan === 4) {
	    var blank_cell = document.createElement("td");
	    blank_cell.innerHTML = "&nbsp;";
	    median_row.appendChild(blank_cell);
	}

	charts[charts_index].table.table.appendChild(median_row);
    }

    if (charts[charts_index].options.raw_data_sources.length > 0) {
	var raw_sources_header_row = document.createElement("tr");
	raw_sources_header_row.className = "section";

	var label_cell = document.createElement("th");
	label_cell.align = "left";
	label_cell.colSpan = colspan;
	label_cell.innerHTML = "Raw Data Source(s):";
	raw_sources_header_row.appendChild(label_cell);

	charts[charts_index].table.table.appendChild(raw_sources_header_row);

	var raw_sources_content_row = document.createElement("tr");

	var content_cell = document.createElement("td");
	content_cell.colSpan = colspan;

	charts[charts_index].options.raw_data_sources.map(function(d) {
		var link = document.createElement("a");
		link.href = d;
		link.innerHTML = d.substr(d.lastIndexOf("/") + 1);

		content_cell.appendChild(link);
		content_cell.appendChild(document.createElement("br"));
	    });

	raw_sources_content_row.appendChild(content_cell);

	charts[charts_index].table.table.appendChild(raw_sources_content_row);
    }
}

function fix_y_axis_labels(charts_index) {
    var labels = charts[charts_index].chart.container.selectAll("g.y.axis,g.y2.axis").selectAll("g.tick").selectAll("text");

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

function handle_brush_actions(charts_index) {
    if (charts[charts_index].x.brush.empty()) {
	charts[charts_index].x.brush.extent(charts[charts_index].x.scale.chart.domain());
    }

    if (charts[charts_index].y.brush.empty()) {
	charts[charts_index].y.brush.extent(charts[charts_index].y.scale.chart.domain());
    }

    var x_extent = charts[charts_index].x.brush.extent();
    var y_extent = charts[charts_index].y.brush.extent();

    var x_domain = charts[charts_index].x.scale.zoom.domain();
    var y_domain = charts[charts_index].y.scale.zoom.domain();

    charts[charts_index].x.scale.chart.domain(x_extent);
    charts[charts_index].y.scale.chart.domain(y_extent);

    charts[charts_index].chart.axis.x.chart.call(charts[charts_index].x.axis.chart);
    charts[charts_index].chart.axis.y.chart.call(charts[charts_index].y.axis.chart);

    charts[charts_index].x.slider.call(charts[charts_index].x.brush);
    charts[charts_index].y.slider.call(charts[charts_index].y.brush);

    if (charts[charts_index].stacked) {
	charts[charts_index].chart.container.selectAll("path.area").attr("d", function(d) { return charts[charts_index].functions.area(d.values); });
	charts[charts_index].chart.container.selectAll("line.points").attr("x1", function(d) { return charts[charts_index].x.scale.chart(d.x) })
	    .attr("x2", function(d) { return charts[charts_index].x.scale.chart(d.x) })
	    .attr("y1", function(d) { return charts[charts_index].y.scale.chart(d.y0); })
	    .attr("y2", function(d) { return charts[charts_index].y.scale.chart(d.y + d.y0); });
    } else {
	charts[charts_index].chart.container.selectAll("path.line").attr("d", function(d) { return charts[charts_index].functions.line(d.values); });
	charts[charts_index].chart.container.selectAll("circle.points").attr("cx", function(d) { return charts[charts_index].x.scale.chart(d.x) })
	    .attr("cy", function(d) { return charts[charts_index].y.scale.chart(d.y) });
    }

    fix_y_axis_labels(charts_index);

    if (charts[charts_index].data_model == "timeseries") {
	set_x_axis_timeseries_label(charts_index);
    }
}

function zoom_it(charts_index, zoom) {
    var x_extent = charts[charts_index].x.brush.extent();
    var x_domain = charts[charts_index].x.scale.zoom.domain();

    if (charts[charts_index].data_model == "timeseries") {
	// convert the timestamps into integers for the calculations that follow
	x_extent[0] = +x_extent[0];
	x_extent[1] = +x_extent[1];
	x_domain[0] = +x_domain[0];
	x_domain[1] = +x_domain[1];
    }
    var y_extent = charts[charts_index].y.brush.extent();
    var y_domain = charts[charts_index].y.scale.zoom.domain();

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

    if (charts[charts_index].data_model == "timeseries") {
	// convert the integers back into date objects after the calculations are complete
	x_extent[0] = new Date(Math.floor(x_extent[0]));
	x_extent[1] = new Date(Math.ceil(x_extent[1]));
    }

    charts[charts_index].x.scale.chart.domain(x_extent);
    charts[charts_index].y.scale.chart.domain(y_extent);

    charts[charts_index].x.brush.extent(x_extent);
    charts[charts_index].y.brush.extent(y_extent);

    charts[charts_index].chart.axis.x.chart.call(charts[charts_index].x.axis.chart);
    charts[charts_index].chart.axis.y.chart.call(charts[charts_index].y.axis.chart);

    charts[charts_index].chart.axis.x.zoom.call(charts[charts_index].x.axis.zoom);
    charts[charts_index].chart.axis.y.zoom.call(charts[charts_index].y.axis.zoom);

    charts[charts_index].x.slider.call(charts[charts_index].x.brush);
    charts[charts_index].y.slider.call(charts[charts_index].y.brush);

    if (charts[charts_index].stacked) {
	charts[charts_index].chart.container.selectAll("path.area").attr("d", function(d) { return charts[charts_index].functions.area(d.values); });
	charts[charts_index].chart.container.selectAll("line.points").attr("x1", function(d) { return charts[charts_index].x.scale.chart(d.x) })
	    .attr("x2", function(d) { return charts[charts_index].x.scale.chart(d.x) })
	    .attr("y1", function(d) { return charts[charts_index].y.scale.chart(d.y0); })
	    .attr("y2", function(d) { return charts[charts_index].y.scale.chart(d.y + d.y0); });
    } else {
	charts[charts_index].chart.container.selectAll("path.line").attr("d", function(d) { return charts[charts_index].functions.line(d.values); });
	charts[charts_index].chart.container.selectAll("circle.points").attr("cx", function(d) { return charts[charts_index].x.scale.chart(d.x) })
	    .attr("cy", function(d) { return charts[charts_index].y.scale.chart(d.y) });
    }

    fix_y_axis_labels(charts_index);

    if (charts[charts_index].data_model == "timeseries") {
	set_x_axis_timeseries_label(charts_index);
    }
}
 
function generate_chart(stacked, data_model, location, chart_title, x_axis_title, y_axis_title, options, callback) {
    var charts_index = charts.push(new chart(chart_title, stacked, data_model, x_axis_title, y_axis_title, location, options)) - 1;

    if ((charts[charts_index].data_model == "xy") ||
	(charts[charts_index].data_model == "timeseries") ||
	(charts[charts_index].data_model == "histogram")) {
	console.log("User specified data_model=\"" + charts[charts_index].data_model + "\" for chart \"" + charts[charts_index].chart_title + "\"");
    } else {
	console.log("An unsupported data_model [\"" + charts[charts_index].data_model + "\"] was specified for chart \"" + charts[charts_index].chart_title + "\"");

	// signal that the chart generation is complete (albeit with an error)
	callback();
	return;
    }

    console.log("Beginning to build chart \"" + charts[charts_index].chart_title + "\"...");

    charts[charts_index].dom.div = document.getElementById(location);

    if (charts[charts_index].dom.div == null) {
	console.log("Failed to locate div for \"" + charts[charts_index].chart_title + "\" identified by \"" + charts[charts_index].location + "\"");

	// signal that the chart generation is complete (albeit with an error)
	callback();
	return;
    }

    var table = document.createElement("table");

    var row = document.createElement("tr");
    row.vAlign = 'top';

    var chart_cell = document.createElement("td");
    row.appendChild(chart_cell);

    charts[charts_index].dom.table.location = document.createElement("td");

    row.appendChild(charts[charts_index].dom.table.location);

    table.appendChild(row);

    charts[charts_index].dom.div.appendChild(table);

    charts[charts_index].dom.div = d3.select(charts[charts_index].dom.div);

    if (charts[charts_index].options.x.scale.linear) {
	charts[charts_index].x.scale.chart = d3.scale.linear();
	charts[charts_index].x.scale.zoom = d3.scale.linear();
    } else if (charts[charts_index].options.x.scale.time) {
	if (charts[charts_index].options.timezone === "local") {
	    charts[charts_index].x.scale.chart = d3.time.scale();
	    charts[charts_index].x.scale.zoom = d3.time.scale();
	} else {
	    charts[charts_index].options.timezone = "utc";
	    charts[charts_index].x.scale.chart = d3.time.scale.utc();
	    charts[charts_index].x.scale.zoom = d3.time.scale.utc();
	}
    } else if (charts[charts_index].options.x.scale.log) {
	charts[charts_index].x.scale.chart = d3.scale.log();
	charts[charts_index].x.scale.zoom = d3.scale.log();
    }

    charts[charts_index].x.scale.chart.range([0, width]);

    charts[charts_index].x.scale.zoom.clamp(true)
	.range([0, width]);

    if (charts[charts_index].options.y.scale.linear) {
	charts[charts_index].y.scale.chart = d3.scale.linear();
	charts[charts_index].y.scale.zoom = d3.scale.linear();
    } else if (charts[charts_index].options.y.scale.log) {
	charts[charts_index].y.scale.chart = d3.scale.log();
	charts[charts_index].y.scale.zoom = d3.scale.log();
    }

    charts[charts_index].y.scale.chart.range([height, 0]);

    charts[charts_index].y.scale.zoom.clamp(true)
	.range([height, 0]);

    charts[charts_index].x.axis.chart = d3.svg.axis()
	.scale(charts[charts_index].x.scale.chart)
	.orient("bottom")
	.tickSize(-height);

    charts[charts_index].x.axis.zoom = d3.svg.axis()
	.scale(charts[charts_index].x.scale.zoom)
	.orient("top")
	.tickSize(9);

    if (charts[charts_index].options.x.scale.time) {
	if (charts[charts_index].options.timezone == "local") {
	    charts[charts_index].x.axis.chart.tickFormat(local_time_format_tick);
	    charts[charts_index].x.axis.zoom.tickFormat(local_time_format_tick);
	} else {
	    charts[charts_index].x.axis.chart.tickFormat(utc_time_format_tick);
	    charts[charts_index].x.axis.zoom.tickFormat(utc_time_format_tick);
	}
    }

    charts[charts_index].x.brush = d3.svg.brush()
	.x(charts[charts_index].x.scale.zoom);

    charts[charts_index].y.axis.chart = d3.svg.axis()
	.scale(charts[charts_index].y.scale.chart)
	.orient("left")
	.tickSize(-width);

    charts[charts_index].y.axis.zoom = d3.svg.axis()
	.scale(charts[charts_index].y.scale.zoom)
	.orient("right")
	.tickSize(9);

    charts[charts_index].y.brush = d3.svg.brush()
	.y(charts[charts_index].y.scale.zoom);

    if (charts[charts_index].stacked) {
	charts[charts_index].functions.area = d3.svg.area()
	    .x(function(d) { return charts[charts_index].x.scale.chart(d.x); })
	    .y0(function(d) { return charts[charts_index].y.scale.chart(d.y0); })
	    .y1(function(d) { return charts[charts_index].y.scale.chart(d.y0 + d.y); });

	charts[charts_index].functions.stack = d3.layout.stack()
	    .values(function(d) { return d.values; });
    } else {
	charts[charts_index].functions.line = d3.svg.line()
	    .x(function(d) { return charts[charts_index].x.scale.chart(d.x); })
	    .y(function(d) { return charts[charts_index].y.scale.chart(d.y); });
    }

    charts[charts_index].chart.svg = d3.select(chart_cell).append("svg")
	.attr("class", "svg")
	.attr("id", location + "_svg")
	.attr("width", width + margin.left + margin.right)
	.attr("height", height + margin.top + margin.bottom + ((Math.ceil(charts[charts_index].dataset_count / legend_properties.columns) - 1 + charts[charts_index].options.legend_entries.length) * legend_properties.row_height));

    charts[charts_index].chart.container = charts[charts_index].chart.svg.append("g")
	.attr("transform", "translate(" + margin.left + ", " + margin.top +")");

    charts[charts_index].chart.container.append("rect")
	.attr("class", "titlebox")
	.attr("x", -margin.left)
	.attr("y", -margin.top)
	.attr("width", width + margin.left + margin.right + 2)
	.attr("height", 15);

    charts[charts_index].chart.container.append("text")
	.attr("class", "title")
	.attr("x", (width/2))
	.attr("y", -margin.top + 11)
	.style("text-anchor", "middle")
	.text(charts[charts_index].chart_title);

    charts[charts_index].chart.container.append("text")
	.attr("class", "actionlabel")
	.attr("x", width + margin.right - 10)
	.attr("y", -margin.top + 29)
	.style("text-anchor", "end")
	.on("click", function() {
		charts[charts_index].x.scale.chart.domain(charts[charts_index].x.scale.zoom.domain());
		charts[charts_index].y.scale.chart.domain(charts[charts_index].y.scale.zoom.domain());

		charts[charts_index].x.brush.extent(charts[charts_index].x.scale.zoom.domain());
		charts[charts_index].y.brush.extent(charts[charts_index].y.scale.zoom.domain());

		charts[charts_index].chart.axis.x.chart.call(charts[charts_index].x.axis.chart);
		charts[charts_index].chart.axis.x.zoom.call(charts[charts_index].x.axis.zoom);

		charts[charts_index].chart.axis.y.chart.call(charts[charts_index].y.axis.chart);
		charts[charts_index].chart.axis.y.zoom.call(charts[charts_index].y.axis.zoom);

		charts[charts_index].x.slider.call(charts[charts_index].x.brush);
		charts[charts_index].y.slider.call(charts[charts_index].y.brush);

		if (charts[charts_index].stacked) {
		    charts[charts_index].chart.container.selectAll("path.area").attr("d", function(d) { return charts[charts_index].functions.area(d.values); });
		    charts[charts_index].chart.container.selectAll("line.points").attr("x1", function(d) { return x(d.x) })
			.attr("x2", function(d) { return charts[charts_index].x.scale.chart(d.x) })
			.attr("y1", function(d) { return charts[charts_index].y.scale.chart(d.y0); })
			.attr("y2", function(d) { return charts[charts_index].y.scale.chart(d.y + d.y0); });
		} else {
		    charts[charts_index].chart.container.selectAll("path.line").attr("d", function(d) { return charts[charts_index].functions.line(d.values); });
		    charts[charts_index].chart.container.selectAll("circle.points").attr("cx", function(d) { return charts[charts_index].x.scale.chart(d.x) })
			.attr("cy", function(d) { return charts[charts_index].y.scale.chart(d.y) });
		}

		fix_y_axis_labels(charts_index);

		if (charts[charts_index].data_model == "timeseries") {
		    set_x_axis_timeseries_label(charts_index);
		}

		charts[charts_index].state.user_x_zoomed = false;
		charts[charts_index].state.user_y_zoomed = false;
	    })
	.text("Reset Zoom/Pan");

    charts[charts_index].chart.container.append("text")
	.attr("class", "actionlabel")
	.attr("x", (-margin.left/2))
	.attr("y", (height + 30))
	.attr("text-anchor", "middle")
	.on("click", function() {
		alert(help);
	    })
	.text("Help");

    // make sure that the library was properly loaded prior to adding the "Save as PNG" link
    if (typeof saveSvgAsPng == 'function') {
	charts[charts_index].chart.container.append("text")
	    .attr("class", "actionlabel")
	    .attr("x", (width / 4) * 2)
	    .attr("y", -margin.top + 29)
	    .style("text-anchor", "middle")
	    .on("click", function() {
		saveSvgAsPng(document.getElementById(location + "_svg"), charts[charts_index].chart_title + ".png", {
		    backgroundColor: "#FFFFFF"
		});
	    })
	    .text("Save as PNG");
    }

    charts[charts_index].chart.show_all = charts[charts_index].chart.container.append("text")
	.attr("class", "actionlabel")
	.attr("x", (width / 4 * 3 - 41))
	.attr("y", -margin.top + 29)
	.style("text-anchro", "middle")
	.text("Show");

    charts[charts_index].chart.container.append("text")
	.attr("x", (width / 4 * 3 - 10))
	.attr("y", -margin.top + 29)
	.style("text-anchro", "middle")
	.text("/");

    charts[charts_index].chart.hide_all = charts[charts_index].chart.container.append("text")
	.attr("class", "actionlabel")
	.attr("x", (width / 4 * 3 + 15))
	.attr("y", -margin.top + 29)
	.style("text-anchor", "middle")
	.text("Hide");

    charts[charts_index].chart.container.append("text")
	.attr("x", (width / 4 * 3 + 42))
	.attr("y", -margin.top + 29)
	.style("text-anchor", "middle")
	.text("All");

    charts[charts_index].chart.container.append("text")
	.attr("class", "actionlabel")
	.attr("x", (width / 4))
	.attr("y", -margin.top + 29)
	.style("text-anchor", "middle")
	.on("click", function() {
		var string = "\"" + charts[charts_index].chart_title + "\"\n\"" + charts[charts_index].x.axis.title.text + "\"";
		var x_values = [];
		charts[charts_index].datasets.map(function(d) {
			string = string + ",\"" + d.name + " (" + charts[charts_index].y.axis.title.text + ")\"";

			// create a temporary placeholder for storing
			// the next index to start searching at below
			d.tmp_index = 0;

			d.values.map(function(b) {
				x_values.push(b.x);
			    });
		    });
		string = string + "\n";

		x_values.sort(function(a, b) { return a - b; });

		var x_domain = charts[charts_index].x.scale.chart.domain();

		for (var i=0; i<x_values.length; i++) {
		    // skip repeated x_values
		    if ((i > 0) && (x_values[i] == x_values[i-1])) {
			continue;
		    }

		    if ((x_values[i] >= x_domain[0]) &&
			(x_values[i] <= x_domain[1])) {
			string = string + x_values[i] + ",";

			for (var d=0; d<charts[charts_index].datasets.length; d++) {
			    //console.log("d=" + d);
			    for (var b=charts[charts_index].datasets[d].tmp_index; b<charts[charts_index].datasets[d].values.length; b++) {
				if (charts[charts_index].datasets[d].values[b].x == x_values[i]) {
				    string = string + charts[charts_index].datasets[d].values[b].y;
				    // store the next index to start searching at
				    charts[charts_index].datasets[d].tmp_index = b + 1;
				    break;
				}
			    }

			    string = string + ",";
			}

			string = string + "\n";
		    }
		}

		create_download(charts[charts_index].chart_title + '.csv', 'text/csv', 'utf-8', string);
	    })
	.text("Export Data as CSV");

    charts[charts_index].chart.container.append("text")
	.attr("class", "actionlabel")
	.attr("x", (width - 10))
	.attr("y", (height + 30))
	.attr("text-anchor", "middle")
	.on("click", function() {
		var x_domain = charts[charts_index].x.scale.chart.domain();

		charts.map(function(d) {
			if (d.chart.container == charts[charts_index].chart.container) {
			    // skip applying zoom to myself
			    return;
			}

			var target_domain = d.x.scale.zoom.domain();
			var source_domain = charts[charts_index].x.scale.zoom.domain();

			var domain_check = 0;

			if (charts[charts_index].data_model == "timeseries") {
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
			    console.log("Skipping application of X-Axis zoom from \"" + charts[charts_index].chart_title + "\" to \"" + d.chart_title + "\" because data domains are not a match");
			    return;
			}

			d.x.scale.chart.domain(x_domain);

			d.x.brush.extent(x_domain);

			d.chart.axis.x.chart.call(d.x.axis.chart);

			d.x.slider.call(d.x.brush);

			if (d.stacked) {
			    d.chart.container.selectAll("path.area").attr("d", function(b) { return d.functions.area(b.values); });
			    charts[charts_index].chart.container.selectAll("line.points").attr("x1", function(d) { return charts[charts_index].x.scale.chart(d.x) })
				.attr("x2", function(d) { return charts[charts_index].x.scale.chart(d.x) })
				.attr("y1", function(d) { return charts[charts_index].y.scale.chart(d.y0); })
				.attr("y2", function(d) { return charts[charts_index].y.scale.chart(d.y + d.y0); });
			} else {
			    d.chart.container.selectAll("path.line").attr("d", function(b) { return d.functions.line(b.values); });
			    charts[charts_index].chart.container.selectAll("circle.points").attr("cx", function(d) { return charts[charts_index].x.scale.chart(d.x) })
				.attr("cy", function(d) { return charts[charts_index].y.scale.chart(d.y) });
			}

			fix_y_axis_labels(charts_index);
		    });
	    })
	.text("Apply X-Axis Zoom to All");

    charts[charts_index].chart.axis.x.chart = charts[charts_index].chart.container.append("g")
	.attr("class", "x axis")
	.attr("transform", "translate(0," + height +")")
	.call(charts[charts_index].x.axis.chart);

    charts[charts_index].x.axis.title.dom = charts[charts_index].chart.axis.x.chart.append("text")
	.attr("class", "axislabel")
	.attr("y", 30)
	.attr("x", (width/2))
	.style("text-anchor", "middle")
	.text(charts[charts_index].x.axis.title.text);

    charts[charts_index].chart.axis.x.zoom = charts[charts_index].chart.container.append("g")
	.attr("class", "x2 axis")
	.attr("transform", "translate(0, -15)")
	.call(charts[charts_index].x.axis.zoom);

    var x_arc = d3.svg.arc()
	.outerRadius(10)
	.startAngle(function(d, i) { if (i) { return Math.PI; } else { return 0; } })
	.endAngle(function(d, i) { if (i) { return 2 * Math.PI; } else { return Math.PI; } });

    charts[charts_index].x.slider = charts[charts_index].chart.container.append("g")
	.attr("class", "x slider")
	.call(charts[charts_index].x.brush);

    charts[charts_index].x.slider.selectAll(".resize").append("path")
	.attr("transform", "translate(0, -15)")
	.attr("d", x_arc);

    charts[charts_index].x.slider.selectAll("rect")
	.attr("transform", "translate(0, -25)")
	.attr("height", 20);

    charts[charts_index].chart.axis.y.chart = charts[charts_index].chart.container.append("g")
	.attr("class", "y axis")
	.call(charts[charts_index].y.axis.chart);

    charts[charts_index].y.axis.title.dom = charts[charts_index].chart.axis.y.chart.append("text")
	.attr("class", "axislabel")
	.attr("x", -margin.left + 10)
	.attr("y", -40)
	.style("text-anchor", "start")
	.text(charts[charts_index].y.axis.title.text);

    charts[charts_index].chart.axis.y.zoom = charts[charts_index].chart.container.append("g")
	.attr("class", "y2 axis")
	.attr("transform", "translate(" + (width + 15) + ", 0)")
	.call(charts[charts_index].y.axis.zoom);

    var y_arc = d3.svg.arc()
	.outerRadius(10)
	.startAngle(function(d, i) { if (i) { return 0.5 * Math.PI; } else { return -0.5 * Math.PI; } })
	.endAngle(function(d, i) { if (i) { return 1.5 * Math.PI; } else { return 0.5 * Math.PI; } });

    charts[charts_index].y.slider = charts[charts_index].chart.container.append("g")
	.attr("class", "y slider")
	.call(charts[charts_index].y.brush);

    charts[charts_index].y.slider.selectAll(".resize").append("path")
	.attr("transform", "translate(" + (width+15) + ", 0)")
	.attr("d", y_arc);

    charts[charts_index].y.slider.selectAll("rect")
	.attr("transform", "translate(" + (width + 5) + ", 0)")
	.attr("width", 20);

    charts[charts_index].chart.show_all.attr("onclick", "show_all(" + charts_index + ");");
    charts[charts_index].chart.hide_all.attr("onclick", "hide_all(" + charts_index + ");");

    charts[charts_index].x.brush.on("brush", function() {
	    if (d3.event.sourceEvent == null) {
		charts[charts_index].x.brush.extent(charts[charts_index].x.scale.chart.domain());
		charts[charts_index].x.slider.call(charts[charts_index].x.brush);
		return;
	    }

	    handle_brush_actions(charts_index);

	    charts[charts_index].state.user_x_zoomed = true;
	});

    charts[charts_index].y.brush.on("brush", function() {
	    if (d3.event.sourceEvent == null) {
		charts[charts_index].y.brush.extent(charts[charts_index].y.scale.chart.domain());
		charts[charts_index].y.slider.call(charts[charts_index].y.brush);
		return;
	    }

	    handle_brush_actions(charts_index);

	    charts[charts_index].state.user_y_zoomed = true;
	});

    var x_domain = charts[charts_index].x.scale.chart.domain();
    var y_domain = charts[charts_index].y.scale.chart.domain();

    charts[charts_index].chart.container.append("clipPath")
	.attr("id", "clip")
	.append("rect")
	.attr("x", charts[charts_index].x.scale.chart(x_domain[0]))
	.attr("y", charts[charts_index].y.scale.chart(y_domain[1]))
	.attr("width", charts[charts_index].x.scale.chart(x_domain[1]) - charts[charts_index].x.scale.chart(x_domain[0]))
	.attr("height", charts[charts_index].y.scale.chart(y_domain[0]) - charts[charts_index].y.scale.chart(y_domain[1]));

    charts[charts_index].chart.container.append("rect")
	.attr("id", "pane")
	.attr("class", "pane")
	.attr("width", width)
	.attr("height", height)
	.on("mousedown", function() {
		if (d3.event.button != 0) {
		    return;
		}

		charts[charts_index].state.selection_start = d3.mouse(this);

		if (charts[charts_index].chart.selection) {
		    charts[charts_index].chart.selection.remove();
		    charts[charts_index].chart.selection = null;
		}

		charts[charts_index].chart.selection = charts[charts_index].chart.container.insert("rect", "#coordinates")
		    .attr("id", "selection")
		    .attr("class", "selection")
		    .attr("x", 0)
		    .attr("y", 0)
		    .attr("width", 1)
		    .attr("height", 1)
		    .style("visibility", "hidden");

		charts[charts_index].state.selection_active = true;
	    })
	.on("mouseup", function() {
		if ((d3.event.button != 0) ||
		    !charts[charts_index].state.selection_active) {
		    return;
		}

		charts[charts_index].state.selection_stop = d3.mouse(this);

		charts[charts_index].chart.selection.remove();
		charts[charts_index].chart.selection = null;

		charts[charts_index].state.selection_active = false;

		if ((charts[charts_index].state.selection_start[0] == charts[charts_index].state.selection_stop[0]) ||
		    (charts[charts_index].state.selection_start[1] == charts[charts_index].state.selection_stop[1])) {
		    return;
		}

		var x_extent = Array(0, 0), y_extent = Array(0, 0);

		if (charts[charts_index].state.selection_start[0] < charts[charts_index].state.selection_stop[0]) {
		    x_extent[0] = charts[charts_index].x.scale.chart.invert(charts[charts_index].state.selection_start[0]);
		    x_extent[1] = charts[charts_index].x.scale.chart.invert(charts[charts_index].state.selection_stop[0]);
		} else {
		    x_extent[0] = charts[charts_index].x.scale.chart.invert(charts[charts_index].state.selection_stop[0]);
		    x_extent[1] = charts[charts_index].x.scale.chart.invert(charts[charts_index].state.selection_start[0]);
		}

		if (charts[charts_index].state.selection_start[1] < charts[charts_index].state.selection_stop[1]) {
		    y_extent[1] = charts[charts_index].y.scale.chart.invert(charts[charts_index].state.selection_start[1]);
		    y_extent[0] = charts[charts_index].y.scale.chart.invert(charts[charts_index].state.selection_stop[1]);
		} else {
		    y_extent[1] = charts[charts_index].y.scale.chart.invert(charts[charts_index].state.selection_stop[1]);
		    y_extent[0] = charts[charts_index].y.scale.chart.invert(charts[charts_index].state.selection_start[1]);
		}

		charts[charts_index].x.brush.extent(x_extent);
		charts[charts_index].y.brush.extent(y_extent);

		charts[charts_index].x.scale.chart.domain(x_extent);
		charts[charts_index].y.scale.chart.domain(y_extent);

		charts[charts_index].chart.axis.x.chart.call(charts[charts_index].x.axis.chart);
		charts[charts_index].chart.axis.y.chart.call(charts[charts_index].y.axis.chart);

		charts[charts_index].x.slider.call(charts[charts_index].x.brush);
		charts[charts_index].y.slider.call(charts[charts_index].y.brush);

		if (charts[charts_index].stacked) {
		    charts[charts_index].chart.container.selectAll("path.area").attr("d", function(d) { return charts[charts_index].functions.area(d.values); });
		    charts[charts_index].chart.container.selectAll("line.points").attr("x1", function(d) { return charts[charts_index].x.scale.chart(d.x) })
			.attr("x2", function(d) { return charts[charts_index].x.scale.chart(d.x) })
			.attr("y1", function(d) { return charts[charts_index].y.scale.chart(d.y0); })
			.attr("y2", function(d) { return charts[charts_index].y.scale.chart(d.y + d.y0); });
		} else {
		    charts[charts_index].chart.container.selectAll("path.line").attr("d", function(d) { return charts[charts_index].functions.line(d.values); });
		    charts[charts_index].chart.container.selectAll("circle.points").attr("cx", function(d) { return charts[charts_index].x.scale.chart(d.x) })
			.attr("cy", function(d) { return charts[charts_index].y.scale.chart(d.y) });
		}

		fix_y_axis_labels(charts_index);

		if (charts[charts_index].data_model == "timeseries") {
		    set_x_axis_timeseries_label(charts_index);
		}

		if (charts[charts_index].data_model == "timeseries") {
		    if (charts[charts_index].options.timezone == "local") {
			charts[charts_index].chart.container.select("#coordinates").style("visibility", "visible")
			    .text("x:" + local_time_format_print(charts[charts_index].x.scale.chart.invert(charts[charts_index].state.selection_stop[0])) +
				  " y:" + table_format_print(charts[charts_index].y.scale.chart.invert(charts[charts_index].state.selection_stop[1])));
		    } else {
			charts[charts_index].chart.container.select("#coordinates").style("visibility", "visible")
			    .text("x:" + utc_time_format_print(charts[charts_index].x.scale.chart.invert(charts[charts_index].state.selection_stop[0])) +
				  " y:" + table_format_print(charts[charts_index].y.scale.chart.invert(charts[charts_index].state.selection_stop[1])));
		    }
		} else {
		    charts[charts_index].chart.container.select("#coordinates").style("visibility", "visible")
			.text("x:" + table_format_print(charts[charts_index].x.scale.chart.invert(charts[charts_index].state.selection_stop[0])) +
			      " y:" + table_format_print(charts[charts_index].y.scale.chart.invert(charts[charts_index].state.selection_stop[1])));
		}

		charts[charts_index].state.user_x_zoomed = true;
		charts[charts_index].state.user_y_zoomed = true;
	    })
	.on("mouseout", function() {
		charts[charts_index].chart.container.selectAll("#coordinates,#xcursorline,#ycursorline,#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		charts[charts_index].chart.container.select("#selection").remove();
		charts[charts_index].state.selection_active = false;
	    })
	.on("mousemove", function() {
		var mouse = d3.mouse(this);

		charts[charts_index].chart.container.selectAll("#zoomin,#zoomout,#playpause,#coordinates,#xcursorline,#ycursorline").style("visibility", "visible");

		if (charts[charts_index].data_model == "timeseries") {
		    if (charts[charts_index].options.timezone == "local") {
			charts[charts_index].chart.container.select("#coordinates").text("x:" + local_time_format_print(charts[charts_index].x.scale.chart.invert(mouse[0])) +
										   " y:" + table_format_print(charts[charts_index].y.scale.chart.invert(mouse[1])));
		    } else {
			charts[charts_index].chart.container.select("#coordinates").text("x:" + utc_time_format_print(charts[charts_index].x.scale.chart.invert(mouse[0])) +
										   " y:" + table_format_print(charts[charts_index].y.scale.chart.invert(mouse[1])));
		    }
		} else {
		    charts[charts_index].chart.container.select("#coordinates").text("x:" + table_format_print(charts[charts_index].x.scale.chart.invert(mouse[0])) +
									       " y:" + table_format_print(charts[charts_index].y.scale.chart.invert(mouse[1])));
		}

		var domain = charts[charts_index].y.scale.chart.domain();

		charts[charts_index].chart.container.select("#xcursorline").attr("x1", mouse[0])
		    .attr("x2", mouse[0])
		    .attr("y1", charts[charts_index].y.scale.chart(domain[1]))
		    .attr("y2", charts[charts_index].y.scale.chart(domain[0]));

		domain = charts[charts_index].x.scale.chart.domain();

		charts[charts_index].chart.container.select("#ycursorline").attr("x1", charts[charts_index].x.scale.chart(domain[0]))
		    .attr("x2", charts[charts_index].x.scale.chart(domain[1]))
		    .attr("y1", mouse[1])
		    .attr("y2", mouse[1]);

		if (charts[charts_index].chart.selection && (charts[charts_index].chart.selection.size() == 1)) {
		    var selection_x, selection_y,
			selection_width, selection_height;

		    if (charts[charts_index].state.selection_start[0] < mouse[0]) {
			selection_x = charts[charts_index].state.selection_start[0];
			selection_width = mouse[0] - charts[charts_index].state.selection_start[0];
		    } else {
			selection_x = mouse[0];
			selection_width = charts[charts_index].state.selection_start[0] - mouse[0];
		    }

		    if (charts[charts_index].state.selection_start[1] < mouse[1]) {
			selection_y = charts[charts_index].state.selection_start[1];
			selection_height = mouse[1] - charts[charts_index].state.selection_start[1];
		    } else {
			selection_y = mouse[1];
			selection_height = charts[charts_index].state.selection_start[1] - mouse[1];
		    }

		    charts[charts_index].chart.selection.attr("x", selection_x)
			.attr("y", selection_y)
			.attr("width", selection_width)
			.attr("height", selection_height)
			.style("visibility", "visible");
		}
	    });

    charts[charts_index].chart.loading = charts[charts_index].chart.container.append("text")
	.attr("class", "loadinglabel")
	.attr("x", (charts[charts_index].x.scale.chart(x_domain[1]) - charts[charts_index].x.scale.chart(x_domain[0])) / 2)
	.attr("y", (charts[charts_index].y.scale.chart(y_domain[0]) - charts[charts_index].y.scale.chart(y_domain[1])) / 2 + 35)
	.style("text-anchor", "middle")
	.text("Loading");

    //console.time("\"" + chart_title + "\" Data Load");

    if (charts[charts_index].options.csvfiles) {
	// this path can have no parallelism since it is unknown how
	// many datasets each CSV file might contain
	charts[charts_index].datasets_queue = d3_queue.queue(1);

	for (var i=0; i<charts[charts_index].options.csvfiles.length; i++) {
	    // add a dataset load to the queue
	    charts[charts_index].datasets_queue.defer(load_csv_files, charts[charts_index].options.csvfiles[i], charts_index);
	}
    } else {
	// this path can have some parallelism, but place a limit on
	// it to keep things under control
	charts[charts_index].datasets_queue = d3_queue.queue(512);

	if (charts[charts_index].options.packed && charts[charts_index].options.plotfile) {
	    // add a packed dataset load to the queue
	    charts[charts_index].datasets_queue.defer(load_plot_file, charts[charts_index].options.plotfile, charts_index);
	} else {
	    if (charts[charts_index].options.plotfiles) {
		for (var i=0; i<charts[charts_index].options.plotfiles.length; i++) {
		    // add a dataset load to the queue
		    charts[charts_index].datasets_queue.defer(load_plot_files, charts[charts_index].options.plotfiles[i], charts_index, i);
		}
	    } else {
		if (charts[charts_index].options.json_plotfile) {
		    charts[charts_index].datasets_queue.defer(load_json, charts_index);
		}
	    }
	}
    }

    // block waiting for the queue processing to complete before completing the chart
    charts[charts_index].datasets_queue.await(function(error, results) {
	    //console.timeEnd("\"" + chart_title + "\" Data Load");

	    console.log("Content load complete for chart \"" + charts[charts_index].chart_title + "\".");

	    if (charts[charts_index].datasets.length > charts[charts_index].dataset_count) {
		console.log("Resizing SVG for chart \"" + charts[charts_index].chart_title + "\".");
		charts[charts_index].chart.svg.attr("height", height + margin.top + margin.bottom + ((Math.ceil(charts[charts_index].datasets.length / legend_properties.columns) - 1 + charts[charts_index].options.legend_entries.length) * legend_properties.row_height))
	    }

	    console.log("Creating table entries for chart \"" + charts[charts_index].chart_title + "\"...");

	    create_table_entries(charts_index);
	    console.log("...finished adding table entries for chart \"" + charts[charts_index].chart_title + "\"");

	    if (charts[charts_index].options.update_interval) {
		console.log("Creating table controls for chart \"" + charts[charts_index].chart_title + "\"...");
		create_table_controls(charts_index);
		console.log("...finished adding table controls for chart \"" + charts[charts_index].chart_title + "\"");
	    }

	    console.log("Processing datasets for chart \"" + charts[charts_index].chart_title + "\"...");
	    var errors = complete_chart(charts_index);
	    console.log("...finished processing datasets for chart \"" + charts[charts_index].chart_title + "\"");

	    charts[charts_index].x.slider.call(charts[charts_index].x.brush.event);
	    charts[charts_index].y.slider.call(charts[charts_index].y.brush.event);

	    if (errors) {
		charts[charts_index].chart.loading.text("Load Errors");
	    } else {
		charts[charts_index].chart.loading.remove();
		charts[charts_index].chart.loading = null;
	    }

	    charts[charts_index].chart.zoomout = charts[charts_index].chart.container.append("g")
		.attr("id", "zoomout")
		.attr("class", "chartbutton")
		.style("visibility", "hidden")
		.on("click", function() {
			zoom_it(charts_index, zoom_rate);
			charts[charts_index].state.user_x_zoomed = true;
			charts[charts_index].state.user_y_zoomed = true;
		    })
		.on("mouseout", function() {
			charts[charts_index].chart.container.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		    })
		.on("mouseover", function() {
			charts[charts_index].chart.container.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "visible");
		    });

	    charts[charts_index].chart.zoomout.append("circle")
		.attr("cx", 20)
		.attr("cy", 20)
		.attr("r", 11);

	    charts[charts_index].chart.zoomout.append("text")
		.attr("x", 20)
		.attr("y", 24)
		.style("text-anchor", "middle")
		.text("-");

	    charts[charts_index].chart.zoomin = charts[charts_index].chart.container.append("g")
		.attr("id", "zoomin")
		.attr("class", "chartbutton")
		.style("visibility", "hidden")
		.on("click", function() {
			zoom_it(charts_index, -1 * zoom_rate);
			charts[charts_index].state.user_x_zoomed = true;
			charts[charts_index].state.user_y_zoomed = true;
		    })
		.on("mouseout", function() {
			charts[charts_index].chart.container.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		    })
		.on("mouseover", function() {
			charts[charts_index].chart.container.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "visible");
		    });

	    charts[charts_index].chart.zoomin.append("circle")
		.attr("cx", 50)
		.attr("cy", 20)
		.attr("r", 11);

	    charts[charts_index].chart.zoomin.append("text")
		.attr("x", 50)
		.attr("y", 24)
		.style("text-anchor", "middle")
		.text("+");

	    charts[charts_index].chart.xcursorline = charts[charts_index].chart.container.append("line")
		.attr("id", "xcursorline")
		.attr("class", "cursorline")
		.attr("x1", 0)
		.attr("y1", 0)
		.attr("x2", 1)
		.attr("y2", 1)
		.style("visibility", "hidden");

	    charts[charts_index].chart.ycursorline = charts[charts_index].chart.container.append("line")
		.attr("id", "ycursorline")
		.attr("class", "cursorline")
		.attr("x1", 0)
		.attr("y1", 0)
		.attr("x2", 1)
		.attr("y2", 1)
		.style("visibility", "hidden");

	    charts[charts_index].chart.coordinates = charts[charts_index].chart.container.append("text")
		.attr("id", "coordinates")
		.attr("class", "coordinates")
		.attr("x", width - 5)
		.attr("y", 15)
		.style("text-anchor", "end")
		.style("visibility", "hidden")
		.text("coordinates");

	    console.log("...finished building chart \"" + charts[charts_index].chart_title + "\"");

	    if (charts[charts_index].options.update_interval && charts[charts_index].options.json_plotfile) {
		charts[charts_index].interval = window.setInterval(function() {
		    update_chart(charts_index);
		}, charts[charts_index].options.update_interval * 1000);

		charts[charts_index].chart.playpause = charts[charts_index].chart.container.append("g")
		    .attr("id", "playpause")
		    .attr("class", "chartbutton")
		    .style("visibility", "hidden")
		    .on("click", function() {
			if (charts[charts_index].state.live_update) {
			    charts[charts_index].state.live_update = false;
			    clearInterval(charts[charts_index].interval);
			    //svg.select("#playpauselabel").text("Play");
			} else {
			    charts[charts_index].state.live_update = true;
			    charts[charts_index].interval = window.setInterval(function() {
				update_chart(charts_index);
			    }, charts[charts_index].options.update_interval * 1000);
			    //svg.select("#playpauselabel").text("Pause");
			}
		    })
		    .on("mouseout", function() {
			charts[charts_index].chart.container.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "hidden");
		    })
		    .on("mouseover", function() {
			charts[charts_index].chart.container.selectAll("#zoomin,#zoomout,#playpause").style("visibility", "visible");
		    });

		charts[charts_index].chart.playpause.append("circle")
		    .attr("cx", 35)
		    .attr("cy", 45)
		    .attr("r", 11);

		charts[charts_index].chart.playpause.append("polygon")
		    .attr("class", "playicon")
		    .attr("points", "29,42 29,49 34,45");

		charts[charts_index].chart.playpause.append("line")
		    .attr("class", "pauseicon")
		    .attr("x1", 37)
		    .attr("y1", 41)
		    .attr("x2", 37)
		    .attr("y2", 50);

		charts[charts_index].chart.playpause.append("line")
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

function create_graph(stacked, data_model, location, chart_title, x_axis_title, y_axis_title, options) {
    if (stacked === "stackedAreaChart") {
	stacked = 1;
    } else if (stacked === "lineChart") {
	stacked = 0;
    }

    // add an entry to the chart generating queue
    charts_queue.defer(generate_chart, stacked, data_model, location, chart_title, x_axis_title, y_axis_title, options);
}

function finish_page() {
    // wait for chart generation to complete before logging that it is done and changing the page background
    charts_queue.await(function(error, results) {
	    d3.select("body").style("background-color", "#CCCCCC");
	    console.log("Finished generating all charts");
	});
}

function click_highlight_function(charts_index, datasets_index) {
    if (charts[charts_index].datasets[datasets_index].hidden) {
	return;
    }

    if ((charts[charts_index].state.chart_selection == -1) ||
	(charts[charts_index].state.chart_selection != datasets_index)) {
	if (charts[charts_index].state.chart_selection != -1) {
	    dehighlight(charts_index, charts[charts_index].state.chart_selection);
	    charts[charts_index].datasets[charts[charts_index].state.chart_selection].highlighted = false;
	}
	charts[charts_index].datasets[datasets_index].highlighted = true;
	charts[charts_index].state.chart_selection = datasets_index;
	highlight(charts_index, datasets_index);
    } else {
	charts[charts_index].datasets[datasets_index].highlighted = false;
	charts[charts_index].state.chart_selection = -1;
	dehighlight(charts_index, datasets_index);
    }
}

function mouseover_highlight_function(charts_index, datasets_index) {
    if (charts[charts_index].datasets[datasets_index].hidden) {
	return;
    }

    if (charts[charts_index].state.chart_selection == -1) {
	highlight(charts_index, datasets_index);
    }
}

function mouseout_highlight_function(charts_index, datasets_index) {
    if (charts[charts_index].datasets[datasets_index].hidden) {
	return;
    }

    if (charts[charts_index].state.chart_selection == -1) {
	dehighlight(charts_index, datasets_index);
    }
}

function highlight(charts_index, datasets_index) {
    charts[charts_index].datasets[datasets_index].dom.legend.label.style("font-weight", "bold");

    if (charts[charts_index].stacked) {
	for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	    if (charts[charts_index].datasets[i].hidden) {
		continue;
	    }

	    if (i == datasets_index) {
		charts[charts_index].datasets[i].dom.path.style("opacity", "0.9");

		if (charts[charts_index].datasets[i].dom.points) {
		    charts[charts_index].datasets[i].dom.points.style("opacity", "0.9")
			.style("stroke-width", "5.0px");
		}

	    } else {
		charts[charts_index].datasets[i].dom.path.style("opacity", "0.15");

		if (charts[charts_index].datasets[i].dom.points) {
		    charts[charts_index].datasets[i].dom.points.style("opacity", "0.15");
		}
	    }
	}
    } else {
	for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	    if (charts[charts_index].datasets[i].hidden) {
		continue;
	    }

	    if (i == datasets_index) {
		charts[charts_index].datasets[i].dom.path.style("opacity", "0.9")
		    .style("stroke-width", "3.0px");

		if (charts[charts_index].datasets[i].dom.points) {
		    charts[charts_index].datasets[i].dom.points.style("opacity", "0.9")
			.attr("r", 4);
		}
	    } else {
		charts[charts_index].datasets[i].dom.path.style("opacity", "0.15")
		    .style("stroke-width", "1.5px");

		if (charts[charts_index].datasets[i].dom.points) {
		    charts[charts_index].datasets[i].dom.points.style("opacity", "0.15");
		}
	    }
	}
    }

    for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	if (charts[charts_index].datasets[i].hidden) {
	    continue;
	}

	if (i == datasets_index) {
	    charts[charts_index].datasets[i].dom.legend.rect.style("opacity", "0.9");
	} else {
	    charts[charts_index].datasets[i].dom.legend.rect.style("opacity", "0.15");
	}
    }

    charts[charts_index].datasets[datasets_index].dom.table.row.style("background-color", "black")
	.style("color", "white");
}

function dehighlight(charts_index, datasets_index) {
    charts[charts_index].datasets[datasets_index].dom.legend.label.style("font-weight", "normal");

    if (charts[charts_index].stacked) {
	for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	    if (charts[charts_index].datasets[i].hidden) {
		continue;
	    }

	    charts[charts_index].datasets[i].dom.path.style("opacity", "0.9");

	    if (charts[charts_index].datasets[i].dom.points) {
		charts[charts_index].datasets[i].dom.points.style("opacity", "0.9")
		    .style("stroke-width", "3.0px");
	    }
	}
    } else {
	for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	    if (charts[charts_index].datasets[i].hidden) {
		continue;
	    }

	    charts[charts_index].datasets[i].dom.path.style("opacity", "0.9")
		.style("stroke-width", "1.5px");

	    if (charts[charts_index].datasets[i].dom.points) {
		charts[charts_index].datasets[i].dom.points.style("opacity", "0.9")
		    .attr("r", 3);
	    }
	}
    }

    for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	if (charts[charts_index].datasets[i].hidden) {
	    continue;
	}

	charts[charts_index].datasets[i].dom.legend.rect.style("opacity", "0.9");
    }

    charts[charts_index].datasets[datasets_index].dom.table.row.style("background-color", "rgba(0, 0, 0, 0)")
	.style("color", "black");
}

function tooltip_on(d, i) {
    var object = d3.select(this);
    var svg = d3.select(object[0][0].ownerSVGElement);
    var coordinates = d3.mouse(object[0][0].ownerSVGElement);

    var string = d.name;

    if (!isNaN(string)) {
	string = tooltip_format_print(d);
    }

    d.dom.tooltip = svg.append("g");

    var text = d.dom.tooltip.append("text")
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
    d.dom.tooltip.insert("rect", ".tooltip")
	.attr("class", "tooltip")
	.attr("x", dimensions.x - tooltip_margin)
	.attr("y", dimensions.y - tooltip_margin)
	.attr("rx", 10)
	.attr("ry", 10)
	.attr("width", dimensions.width + 2 * tooltip_margin)
	.attr("height", dimensions.height + 2 * tooltip_margin);
}

function tooltip_off(d, i) {
    d.dom.tooltip.remove();
    d.dom.tooltip = null;
}

function set_x_axis_timeseries_label(charts_index) {
    var label = "Time ";

    var domain = charts[charts_index].x.scale.chart.domain();

    if (charts[charts_index].options.timezone == "local") {
	label += "(" + timezone_print(domain[0]) + "): " + local_time_format_print(domain[0]) + " - " + local_time_format_print(domain[1]);
    } else {
	label += "(UTC/GMT): " + utc_time_format_print(domain[0]) + " - " + utc_time_format_print(domain[1]);
    }

    charts[charts_index].x.axis.title.dom.text(label);
}

function show_all(charts_index) {
    var opacity;

    for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	if (charts[charts_index].datasets[i].hidden) {
	    charts[charts_index].datasets[i].hidden = false;
	    charts[charts_index].datasets[i].dom.path.style("visibility", "visible");
	    if (charts[charts_index].datasets[i].dom.points) {
		charts[charts_index].datasets[i].dom.points.style("visibility", "visible");
	    }
	    charts[charts_index].datasets[i].dom.legend.rect.style("opacity", "0.9");
	    charts[charts_index].datasets[i].dom.table.row.style("background-color", "rgba(0, 0, 0, 0)");
	}
    }

    if (charts[charts_index].state.chart_selection != -1) {
	highlight(charts_index, charts[charts_index].state.chart_selection);
    }
}

function hide_all(charts_index) {
    if (charts[charts_index].state.chart_selection != -1) {
	click_highlight_function(charts_index, charts[charts_index].state.chart_selection);
    }

    for (var i = 0; i < charts[charts_index].datasets.length; i++) {
	if (! charts[charts_index].datasets[i].hidden) {
	    charts[charts_index].datasets[i].hidden = true;
	    charts[charts_index].datasets[i].dom.path.style("visibility", "hidden");
	    if (charts[charts_index].datasets[i].dom.points) {
		charts[charts_index].datasets[i].dom.points.style("visibility", "hidden");
	    }
	    charts[charts_index].datasets[i].dom.legend.rect.style("opacity", "0");
	    charts[charts_index].datasets[i].dom.table.row.style("background-color", "rgba(152, 152, 152, 1)");
	}
    }
}

function toggle_hide(charts_index, datasets_index) {
    if (charts[charts_index].datasets[datasets_index].hidden) {
	charts[charts_index].datasets[datasets_index].hidden = false;
	charts[charts_index].datasets[datasets_index].dom.path.style("visibility", "visible");
	charts[charts_index].datasets[datasets_index].dom.legend.rect.style("opacity", "0.9");
	charts[charts_index].datasets[datasets_index].dom.table.row.style("background-color", "rgba(0, 0, 0, 0)");

	if (charts[charts_index].state.chart_selection != -1) {
	    charts[charts_index].datasets[datasets_index].dom.legend.rect.style("opacity", "0.15");
	    charts[charts_index].datasets[datasets_index].dom.path.style("opacity", "0.15");
	}
    } else {
	if ((charts[charts_index].state.chart_selection != -1) &&
	    (charts[charts_index].state.chart_selection == datasets_index)) {
	    charts[charts_index].state.chart_selection = -1;
	    dehighlight(charts_index, datasets_index);
	}

	// once this dataset is marked as hidden it will not be
	// capable of executing it's mouseout function so call it
	// manually
	mouseout_highlight_function(charts_index, datasets_index);

	charts[charts_index].datasets[datasets_index].hidden = true;
	charts[charts_index].datasets[datasets_index].dom.path.style("visibility", "hidden");
	charts[charts_index].datasets[datasets_index].dom.legend.rect.style("opacity", "0");
	charts[charts_index].datasets[datasets_index].dom.table.row.style("background-color", "rgba(152, 152, 152, 1)");
    }
}
