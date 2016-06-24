
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

// array to store objects for each chart, with references to often used variables
var charts = [];

// queue to use for generating charts, 1 at a time to limit the total amount of concurrency
var charts_queue = d3.queue(1);

function datapoint(x, y, dataset, timestamp) {
    this.x = x;
    this.y = y;
    this.dataset = dataset;
    this.timestamp = timestamp;
    this.percentile = null;

    if (!this.dataset.max_y_value ||
	(this.dataset.max_y_value < this.y)) {
	this.dataset.max_y_value = this.y;
    }
}

function dataset(index, name, mean, median, values, chart) {
    this.index = index;
    this.chart = chart;
    this.name = name;
    this.mean = mean;
    this.median = median;
    this.highlighted = false;
    this.hidden = false;
    this.invalid = false;
    this.max_y_value = null;
    this.cursor_index = null;
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
			  value: null,
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
		 cursor_point: null,
		 legend: { rect: null,
			   label: null
			 }
	       };
    this.values = [];
}

function chart(charts, title, stacked, data_model, x_axis_title, y_axis_title, location, options) {
    this.charts = charts;
    this.chart_title = title;
    this.charts_index = null;
    this.stacked = stacked;
    this.data_model = data_model;
    this.location = location;
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
		   viewport: null,
		   show_all: null,
		   hide_all: null,
		   selection: null,
		   loading: null,
		   legend: null,
		   plot: null,
		   points: null,
		   cursor_points: null,
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
			 },
		   viewport_controls: null,
		   viewport_elements: null
		 };

    this.dom = { div: null,
		 table: { location: null,
			  table: null,
			  stacked: { median: null,
				     mean: null,
				     value: null
				   },
			  live_update: { history: null,
					 interval: null
				       },
			  threshold: null,
			  name_filter: null,
			  data_rows: null
			}
	       };

    this.table = { stacked_mean: 0,
		   stacked_median: 0,
		   stacked_value: 0
		 };

    this.state = { user_x_zoomed: false,
		   user_y_zoomed: false,
		   chart_selection: -1,
		   selection_start: null,
		   selection_stop: null,
		   selection_active: false,
		   live_update: true,
		   visible_datasets: 0,
		   cursor_value: null,
		   mouse: null
		 };

    this.functions = { area: null,
		       stack: null,
		       line: null
		     };

    this.datasets_queue = null;
    this.datasets = { all: [],
		      valid: []
		    };

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
		     live_update: false,
		     history_length: null,
		     hide_dataset_threshold: null,
		     sort_datasets: true,
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
    this.zoom_rate = 3;
    this.y_axis_overscale = 2;

    this.dimensions = { margin: { top: 70,
				  right: 87,
				  bottom: 66,
				  left: 65
				},
			legend_properties: { columns: 5,
					     row_height: 30,
					     margin: { top: 37
						       }
					   },
			total_width: 1000,
			total_height: 510,
			pixels_per_letter: 7.2
		      };

    this.dimensions.viewport_width = this.dimensions.total_width -
	this.dimensions.margin.left - this.dimensions.margin.right;

    this.dimensions.viewport_height = this.dimensions.total_height -
	this.dimensions.margin.top - this.dimensions.margin.bottom;

    this.formatting = { table: { float: d3.format(" ,.2f"),
				 integer: d3.format(" ,")
			       },
			tooltip: d3.format(" ,f"),
			time: { utc: { long: d3.time.format.utc("%Y-%m-%d %H:%M:%S"),
				       short: d3.time.format.utc("%M:%S")
				     },
				local: { long: d3.time.format("%Y-%m-%d %H:%M:%S"),
					 short: d3.time.format("%M:%S")
				       },
				timezone: d3.time.format("UTC/GMT %Z")
			      }
		      };

    this.parsers = { space: d3.dsv(" ", "text/plain")
		   };

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
	this.options.live_update = true;

	this.options.update_interval = options.update_interval;

	this.options.sort_datasets = false;

	console.log("Cannot enable dataset sorting for \"" + this.chart_title + "\" because it is not compatible with live updates.");
    } else if (options.sort_datasets !== undefined) {
	this.options.sort_datasets = options.sort_datasets;
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

    if (options.threshold !== undefined) {
	this.options.hide_dataset_threshold = options.threshold;
    }
}

function compute_stacked_median(chart) {
    var foo = [];
    var bar = [];

    for (var i=0; i<chart.datasets.valid.length; i++) {
	if (!chart.datasets.valid[i].hidden &&
	    (chart.datasets.valid[i].values !== undefined)) {
	    for (var x=0; x<chart.datasets.valid[i].values.length; x++) {
		if (foo[chart.datasets.valid[i].values[x].x] === undefined) {
		    foo[chart.datasets.valid[i].values[x].x] = 0;
		}

		foo[chart.datasets.valid[i].values[x].x] += chart.datasets.valid[i].values[x].y;
	    }
	}
    }

    for (var key in foo) {
	bar.push(foo[key]);
    }

    if (bar.length > 0) {
	chart.table.stacked_median = d3.median(bar);
    } else {
	chart.table.stacked_median = "No Samples";
    }
}

function compute_stacked_mean(chart) {
    var sum = 0;
    var counter = 0;

    for (var i=0; i<chart.datasets.valid.length; i++) {
	if (!chart.datasets.valid[i].hidden) {
	    if (!isNaN(chart.datasets.valid[i].mean)) {
		sum += chart.datasets.valid[i].mean;
		counter++;;
	    }
	}
    }

    if (counter) {
	chart.table.stacked_mean = sum;
    } else {
	chart.table.stacked_mean = "No Samples";
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

function parse_plot_file(chart, datasets_index, text) {
    chart.datasets.all[datasets_index] = new dataset(datasets_index, "", "No Samples", "No Samples", [], chart);
    chart.state.visible_datasets++;

    var file = chart.parsers.space.parseRows(text);

    for (var i=0; i<file.length; i++) {
	var index = file[i][0].indexOf("#LABEL:");

	if (index == -1) {
	    if (chart.data_model == "histogram") {
		chart.datasets.all[datasets_index].histogram.samples += +file[i][1];
		chart.datasets.all[datasets_index].histogram.sum += (+file[i][0] * +file[i][1]);
	    }
	    chart.datasets.all[datasets_index].values.push(new datapoint(+file[i][0], +file[i][1], chart.datasets.all[datasets_index], null));
	} else {
	    var tmp = file[i][0].substring(7);
	    for (var x=1; x<file[i].length; x++) {
		tmp += " " + file[i][x]
	    }

	    chart.datasets.all[datasets_index].name = tmp;
	}
    }

    if (chart.datasets.all[datasets_index].values.length > 0) {
	chart.datasets.all[datasets_index].mean = d3.mean(chart.datasets.all[datasets_index].values, get_datapoint_y);
	chart.datasets.all[datasets_index].median = d3.median(chart.datasets.all[datasets_index].values, get_datapoint_y);

	if (chart.data_model == "histogram") {
	    chart.datasets.all[datasets_index].histogram.mean = chart.datasets.all[datasets_index].histogram.sum / chart.datasets.all[datasets_index].histogram.samples;
	    chart.datasets.all[datasets_index].histogram.min = chart.datasets.all[datasets_index].values[0].x;
	    chart.datasets.all[datasets_index].histogram.max = chart.datasets.all[datasets_index].values[chart.datasets.all[datasets_index].values.length - 1].x;

	    var count = 0;
	    var threshold = chart.datasets.all[datasets_index].histogram.samples * 0.5;
	    var threshold_p90 = chart.datasets.all[datasets_index].histogram.samples * 0.9;
	    var threshold_p95 = chart.datasets.all[datasets_index].histogram.samples * 0.95;
	    var threshold_p99 = chart.datasets.all[datasets_index].histogram.samples * 0.99;
	    var threshold_p9999 = chart.datasets.all[datasets_index].histogram.samples * 0.9999;
	    for (var i=0; i < chart.datasets.all[datasets_index].values.length; i++) {
		count += chart.datasets.all[datasets_index].values[i].y;
		if ((chart.datasets.all[datasets_index].histogram.median === null) && (count >= threshold)) {
		    chart.datasets.all[datasets_index].histogram.median = chart.datasets.all[datasets_index].values[i].x;
		}
		if ((chart.datasets.all[datasets_index].histogram.p90 === null) && (count >= threshold_p90)) {
		    chart.datasets.all[datasets_index].histogram.p90 = chart.datasets.all[datasets_index].values[i].x;
		}
		if ((chart.datasets.all[datasets_index].histogram.p95 === null) && (count >= threshold_p95)) {
		    chart.datasets.all[datasets_index].histogram.p95 = chart.datasets.all[datasets_index].values[i].x;
		}
		if ((chart.datasets.all[datasets_index].histogram.p99 === null) && (count >= threshold_p99)) {
		    chart.datasets.all[datasets_index].histogram.p99 = chart.datasets.all[datasets_index].values[i].x;
		}
		if ((chart.datasets.all[datasets_index].histogram.p9999 === null) && (count >= threshold_p9999)) {
		    chart.datasets.all[datasets_index].histogram.p9999 = chart.datasets.all[datasets_index].values[i].x;
		}
		chart.datasets.all[datasets_index].values[i].percentile = count / chart.datasets.all[datasets_index].histogram.samples * 100;
	    }
	}
    } else {
	chart.datasets.all[datasets_index].invalid = true;
	chart.datasets.all[datasets_index].hidden = true;

	chart.datasets.all[datasets_index].mean = "No Samples";
	chart.datasets.all[datasets_index].median = "No Samples";

	if (chart.data_model == "histogram") {
	    chart.datasets.all[datasets_index].histogram.mean = "No Samples";
	    chart.datasets.all[datasets_index].histogram.median = "No Samples";
	    chart.datasets.all[datasets_index].histogram.min = "No Samples";
	    chart.datasets.all[datasets_index].histogram.max = "No Samples";
	    chart.datasets.all[datasets_index].histogram.p90 = "No Samples";
	    chart.datasets.all[datasets_index].histogram.p95 = "No Samples";
	    chart.datasets.all[datasets_index].histogram.p99 = "No Samples";
	    chart.datasets.all[datasets_index].histogram.p9999 = "No Samples";
	}
    }

    if (chart.options.hide_dataset_threshold &&
	(chart.datasets.all[i].max_y_value < chart.options.hide_dataset_threshold)) {
	chart.datasets.all[i].hidden = true;
	chart.state.visible_datasets--;
    }
}

function update_domains(chart) {
    chart.x.scale.chart.domain([
	d3.min(chart.datasets.valid, get_dataset_min_x),
	d3.max(chart.datasets.valid, get_dataset_max_x)
    ]);

    var domain = chart.x.scale.chart.domain();

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

    if (chart.options.x.min) {
	domain[0] = chart.options.x.min;
    }

    if (chart.options.x.max) {
	domain[1] = chart.options.x.max;
    }

    chart.x.scale.chart.domain(domain);
    chart.x.scale.zoom.domain(chart.x.scale.chart.domain());

    if (! chart.state.user_x_zoomed) {
	chart.x.brush.extent(domain);
    }

    if (chart.stacked) {
	chart.datasets.valid = chart.functions.stack(chart.datasets.valid);

	chart.y.scale.chart.domain([
	    d3.min(chart.datasets.valid, get_dataset_min_y_stack),
	    d3.max(chart.datasets.valid, get_dataset_max_y_stack)
	]);
    } else {
	chart.y.scale.chart.domain([
	    d3.min(chart.datasets.valid, get_dataset_min_y),
	    d3.max(chart.datasets.valid, get_dataset_max_y)
	]);
    }

    var domain = chart.y.scale.chart.domain();

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

    if (!chart.stacked &&
	!chart.options.y.scale.log &&
	(domain[0] > 0)) {
	domain[0] = 0;
    }

    if (chart.options.y.min) {
	domain[0] = chart.options.y.min;
    }

    if (chart.options.y.max) {
	domain[1] = chart.options.y.max;
    } else {
	domain[1] *= (1 + chart.y_axis_overscale/100);
    }

    chart.y.scale.chart.domain(domain);
    chart.y.scale.zoom.domain(chart.y.scale.chart.domain());

    if (! chart.state.user_y_zoomed) {
	chart.y.brush.extent(domain);
    }
}

function update_chart(chart) {
    if (!chart.state.visible_datasets) {
	return;
    }

    update_domains(chart);

    zoom_it(chart, 0);

    if (chart.stacked) {
	compute_stacked_mean(chart);
	chart.dom.table.stacked.mean.text(table_print(chart, chart.table.stacked_mean));

	compute_stacked_median(chart);
	chart.dom.table.stacked.median.text(table_print(chart, chart.table.stacked_median));
    }
}

function live_update(chart) {
    var last_timestamp = 0;
    if (chart.datasets.valid.length) {
	last_timestamp = chart.datasets.valid[0].last_timestamp;
    }

    var post_data = "time=" + last_timestamp;

    if (chart.options.json_args) {
	post_data += "&" + chart.options.json_args;
    }

    d3.json(chart.options.json_plotfile)
	.header("Content-Type", "application/x-www-form-urlencoded")
	.post(post_data, function(error, json) {
	    if ((json !== undefined) &&
		(json.data_series_names !== undefined) &&
		(json.x_axis_series !== undefined) &&
		(json.data !== undefined)) {
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

		    for (var i=0; i<json.data.length; i++) {
			chart.datasets.valid[dataset_index].values.push(new datapoint(null, json.data[i][index], chart.datasets.valid[dataset_index], json.data[i][0]));
			chart.datasets.valid[dataset_index].last_timestamp = json.data[i][0];
		    }

		    if (chart.options.history_length) {
			var delta = chart.datasets.valid[dataset_index].values.length - chart.options.history_length;

			if (delta > 0) {
			    chart.datasets.valid[dataset_index].values.splice(0, delta);
			}
		    }

		    for (var i=0; i<chart.datasets.valid[dataset_index].values.length; i++) {
			chart.datasets.valid[dataset_index].values[i].x = chart.datasets.valid[dataset_index].values[i].timestamp;
		    }

		    var mean;
		    var median;

		    if (chart.datasets.valid[dataset_index].values.length > 0) {
			mean = d3.mean(chart.datasets.valid[dataset_index].values, get_datapoint_y);
			median = d3.median(chart.datasets.valid[dataset_index].values, get_datapoint_y);
		    } else {
			mean = "No Samples";
			median = "No Samples"
		    }

		    chart.datasets.valid[dataset_index].mean = mean;
		    chart.datasets.valid[dataset_index].median = median;

		    chart.datasets.valid[dataset_index].dom.table.mean.text(chart.formatting.table.float(mean));
		    chart.datasets.valid[dataset_index].dom.table.median.text(chart.formatting.table.float(median));
		    chart.datasets.valid[dataset_index].dom.table.samples.text(chart.datasets.valid[dataset_index].values.length);

		    dataset_index++;
		}

		update_chart(chart);

		// if the chart's cursor_value state is not null that
		// means the cursor is in the viewport; this means the
		// mousemove event must be fired to perform cursor
		// updates to reflect the viewport changes that the
		// live update causes
		if (chart.state.cursor_value) {
		    chart.chart.viewport.on("mousemove")(chart);
		}
	    }
	});
}

function load_json(chart, callback) {
    var post_data = "";

    if (chart.options.json_args) {
	post_data += chart.options.json_args;
    }

    d3.json(chart.options.json_plotfile)
	.header("Content-Type", "application/x-www-form-urlencoded")
	.post(post_data, function(error, json) {
	    if ((json !== undefined) &&
		(json.data_series_names !== undefined) &&
		(json.x_axis_series !== undefined) &&
		(json.data !== undefined)) {
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

		    chart.datasets.all[dataset_index] = new dataset(index-1, json.data_series_names[index], 0, 0, [], chart);

		    for (var i=0; i<json.data.length; i++) {
			chart.datasets.all[dataset_index].values.push(new datapoint(json.data[i][x_axis_index], json.data[i][index], chart.datasets.all[dataset_index], json.data[i][x_axis_index]));
			chart.state.visible_datasets++;
			chart.datasets.all[dataset_index].last_timestamp = json.data[i][x_axis_index];
		    }

		    if (chart.datasets.all[dataset_index].values.length > 0) {
			chart.datasets.all[dataset_index].mean = d3.mean(chart.datasets.all[dataset_index].values, get_datapoint_y);
			chart.datasets.all[dataset_index].median = d3.median(chart.datasets.all[dataset_index].values, get_datapoint_y);
		    } else {
			chart.datasets.all[dataset_index].invalid = true;
			chart.datasets.all[dataset_index].hidden = true;

			chart.datasets.all[dataset_index].mean = "No Samples";
			chart.datasets.all[dataset_index].median = "No Samples";

			if (chart.data_model == "histogram") {
			    chart.datasets.all[datasets_index].histogram.mean = "No Samples";
			    chart.datasets.all[datasets_index].histogram.median = "No Samples";
			    chart.datasets.all[datasets_index].histogram.min = "No Samples";
			    chart.datasets.all[datasets_index].histogram.max = "No Samples";
			    chart.datasets.all[datasets_index].histogram.p90 = "No Samples";
			    chart.datasets.all[datasets_index].histogram.p95 = "No Samples";
			    chart.datasets.all[datasets_index].histogram.p99 = "No Samples";
			    chart.datasets.all[datasets_index].histogram.p9999 = "No Samples";
			}
		    }

		    dataset_index++;
		}

		if (chart.options.hide_dataset_threshold &&
		    (chart.datasets.all[i].max_y_value < chart.options.hide_dataset_threshold)) {
		    chart.datasets.all[i].hidden = true;
		    chart.state.visible_datasets--;
		}
	    }

	    // signal that we are finished asynchronously loading the data
	    callback();
	});
}

function load_csv_files(url, chart, callback) {
    // the call to d3.text is performed asynchronously...queue.js
    // processing is used to ensure all files are loaded prior to
    // populating the graph, avoiding parallelism issues
    d3.text(url, "text/plain")
	.get(function(error, text) {
		var index_base = chart.datasets.all.length;

		if ((text === undefined) ||
		    (error !== null)) {
		    console.log("ERROR: Loading \"%s\" resulted in error \"%O\".", url, error);

		    // create an error object with minimal properties
		    chart.datasets.all[index_base - 1] = new dataset(index_base - 1, "Error loading " + url, "No Samples", "No Samples", [], chart);
		    chart.datasets.all[index_base - 1].invalid = true;
		    chart.datasets.all[index_base - 1].hidden = true;

		    // signal that we are finished asynchronously failing to load the data
		    callback();
		    return;
		}

		var sample_counter = 0;

		var data = d3.csv.parseRows(text);

		// csv_format
		// 1 = ts,d0,d1,d2,...,dN
		// 2 = ts0,d0,ts1,d1,ts2,d2,...,tsN,dN
		var csv_format = 1;
		var incrementer;

		for (var x=0; x<data.length; x++) {
		    if (sample_counter == 0) {
			var timestamp_columns = 0;
			for (var i=0; i<data[x].length; i+=2) {
			    if (data[x][i].startsWith("timestamp_") && data[x][i].endsWith("_ms")) {
				timestamp_columns++;
			    }
			}

			if (timestamp_columns == 1) {
			    csv_format = 1;
			} else if (timestamp_columns > 1) {
			    csv_format = 2;
			}

			if (csv_format == 1) {
			    incrementer = 1;
			} else if (csv_format == 2) {
			    incrementer = 2;
			}

			for (var i=1,counter=0; i<data[x].length; i+=incrementer,counter++) {
			    chart.datasets.all[index_base + counter] = new dataset(index_base + counter, data[x][i], "No Samples", "No Samples", [], chart);
			    chart.state.visible_datasets++;
			}
		    } else {
			var counter = 0;
			var ts_index = 0;

			for (var i=1,counter=0; i<data[x].length; i+=incrementer,counter++) {
			    if (data[x][i] == "") {
				continue;
			    }

			    if (csv_format == 1) {
				ts_index = 0;
			    } else if (csv_format == 2) {
				ts_index = i - 1;
			    }

			    chart.datasets.all[index_base + counter].values.push(new datapoint(+data[x][ts_index], +data[x][i], chart.datasets.all[index_base + counter], null));

			    if (chart.data_model == "histogram") {
				chart.datasets.all[index_base + counter].histogram.samples += +data[x][i];
				chart.datasets.all[index_base + counter].histogram.sum += (+data[x][ts_index] * +data[x][i]);
			    }
			}
		    }

		    sample_counter++;
		}

		for (var i=index_base; i<chart.datasets.all.length; i++) {
		    if (chart.datasets.all[i].values.length) {
			chart.datasets.all[i].mean = d3.mean(chart.datasets.all[i].values, get_datapoint_y);
			chart.datasets.all[i].median = d3.median(chart.datasets.all[i].values, get_datapoint_y);

			if (chart.data_model == "histogram") {
			    chart.datasets.all[i].histogram.mean = chart.datasets.all[i].histogram.sum / chart.datasets.all[i].histogram.samples;
			    chart.datasets.all[i].histogram.min = chart.datasets.all[i].values[0].x;
			    chart.datasets.all[i].histogram.max = chart.datasets.all[i].values[chart.datasets.all[i].values.length - 1].x;

			    var count = 0;
			    var threshold = chart.datasets.all[i].histogram.samples * 0.5;
			    var threshold_p90 = chart.datasets.all[i].histogram.samples * 0.9;
			    var threshold_p95 = chart.datasets.all[i].histogram.samples * 0.95;
			    var threshold_p99 = chart.datasets.all[i].histogram.samples * 0.99;
			    var threshold_p9999 = chart.datasets.all[i].histogram.samples * 0.9999;
			    for (var p=0; p < chart.datasets.all[i].values.length; p++) {
				count += chart.datasets.all[i].values[p].y;
				if ((chart.datasets.all[i].histogram.median === null) && (count >= threshold)) {
				    chart.datasets.all[i].histogram.median = chart.datasets.all[i].values[p].x;
				}
				if ((chart.datasets.all[i].histogram.p90 === null) && (count >= threshold_p90)) {
				    chart.datasets.all[i].histogram.p90 = chart.datasets.all[i].values[p].x;
				}
				if ((chart.datasets.all[i].histogram.p95 === null) && (count >= threshold_p95)) {
				    chart.datasets.all[i].histogram.p95 = chart.datasets.all[i].values[p].x;
				}
				if ((chart.datasets.all[i].histogram.p99 === null) && (count >= threshold_p99)) {
				    chart.datasets.all[i].histogram.p99 = chart.datasets.all[i].values[p].x;
				}
				if ((chart.datasets.all[i].histogram.p9999 === null) && (count >= threshold_p9999)) {
				    chart.datasets.all[i].histogram.p9999 = chart.datasets.all[i].values[p].x;
				}
				chart.datasets.all[i].values[p].percentile = count / chart.datasets.all[i].histogram.samples * 100;
			    }
			}
		    } else {
			chart.datasets.all[i].invalid = true;
			chart.datasets.all[i].hidden = true;
		    }

		    if (chart.options.hide_dataset_threshold &&
			(chart.datasets.all[i].max_y_value < chart.options.hide_dataset_threshold)) {
			chart.datasets.all[i].hidden = true;
			chart.state.visible_datasets--;
		    }
		}

		// signal that we are finished asynchronously loading the data
		callback();
	    });
}

function load_plot_file(url, chart, callback) {
    load_plot_files(url, chart, -1, callback)
}

function load_plot_files(url, chart, index, callback) {
    // the call to d3.text is performed asynchronously...queue.js
    // processing is used to ensure all files are loaded prior to
    // populating the graph, avoiding parallelism issues
    d3.text(url, "text/plain")
	.get(function(error, text) {
		if ((text === undefined) ||
		    (error !== null)) {
		    console.log("ERROR: Loading \"%s\" resulted in error \"%O\".", url, error);

		    // create an error object with minimal properties
		    chart.datasets.all[index] = new dataset(index, "Error loading " + url, "No Samples", "No Samples", [], chart);
		    chart.datasets.all[index].invalid = true;
		    chart.datasets.all[index].hidden = true;

		    // signal that we are finished asynchronously failing to load the data
		    callback();
		    return;
		}

		var packed_separator = "--- JSChart Packed Plot File V1 ---";
		var packed_index = text.indexOf(packed_separator);
		var prev_packed_index = packed_index;
		if ((packed_index == -1) && (index >= 0)) {
		    parse_plot_file(chart, index, text);
		} else {
		    var dataset_index = 0;

		    while (packed_index >= 0) {
			prev_packed_index = packed_index;
			packed_index = text.indexOf(packed_separator, packed_index+1);

			parse_plot_file(chart, dataset_index++, text.slice(prev_packed_index + packed_separator.length + 1, packed_index));
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

function complete_chart(chart) {
    update_domains(chart);

    if (chart.datasets.all.length < chart.dimensions.legend_properties.columns) {
	chart.dimensions.legend_properties.columns = chart.datasets.all.length;
    }

    chart.chart.legend = chart.chart.container.selectAll(".legend")
        .data(chart.datasets.all)
	.enter().append("g")
        .classed("legend", true)
        .attr("transform", function(d, i) { return "translate(" + (-chart.dimensions.margin.left + 5 + (i % chart.dimensions.legend_properties.columns) * (chart.dimensions.total_width / chart.dimensions.legend_properties.columns)) + "," + (chart.dimensions.viewport_height + chart.dimensions.legend_properties.margin.top + (Math.floor(i / chart.dimensions.legend_properties.columns) * chart.dimensions.legend_properties.row_height)) + ")"; });

    chart.chart.legend.append("rect")
	.classed("legendrectoutline", true)
	.attr("width", 16)
	.attr("height", 16)
	.style("stroke", function(d) { return mycolors(d.index); } );

    chart.chart.legend.append("rect")
	.classed("legendrect", function(d) { d.dom.legend.rect = d3.select(this); return true; })
	.on("click", toggle_hide_click_event)
	.on("mouseover", mouseover_highlight_function)
	.on("mouseout", mouseout_highlight_function)
	.attr("width", 12)
	.attr("height", 12)
	.attr("transform", "translate(2, 2)")
	.classed("invisible", function(d) { if (d.hidden) { return true; } else { return false; } })
	.style("fill", function(d) { return mycolors(d.index); } );

    var legend_label_offset = 25;

    chart.chart.legend.append("text")
	.classed("legendlabel", true)
	.on("click", click_highlight_function)
	.on("mouseover", mouseover_highlight_function)
	.on("mouseout", mouseout_highlight_function)
	.attr("x", legend_label_offset)
	.attr("y", 13.5)
	.text(function(d) { d.dom.legend.label = d3.select(this); return d.name; });

    chart.chart.container.selectAll(".legendlabel")
	.each(function(d, i) {
		var label_width = this.getBBox().width;

		if (label_width >= (chart.dimensions.total_width / chart.dimensions.legend_properties.columns - legend_label_offset)) {
		    var label = d3.select(this);

		    label.text(d.name.substr(0, 21) + '...')
			.on("mouseover.tooltip", tooltip_on)
			.on("mouseout.tooltip", tooltip_off);
		}
	    });

    if (chart.options.legend_entries) {
	var legend_entries = chart.chart.container.selectAll(".legendentries")
	    .data(chart.options.legend_entries)
	    .enter().append("g")
	    .classed("legend", true)
	    .attr("transform", function(d, i) { return "translate(" + (-chart.dimensions.margin.left + 5) + ", " + (chart.dimensions.viewport_height + chart.dimensions.legend_properties.margin.top + ((Math.floor(chart.datasets.all.length / chart.dimensions.legend_properties.columns) + i) * chart.dimensions.legend_properties.row_height)) + ")"; });

	legend_entries.append("text")
	    .attr("y", 13.5)
	    .attr("lengthAdjust", "spacingAndGlyphs")
	    .attr("textLength", function(d, i) { if ((d.length * chart.dimensions.pixels_per_letter) >= chart.dimensions.total_width) { return (chart.dimensions.total_width - 5).toFixed(0); } })
	    .text(function(d) { return d; });
    }

    chart.chart.axis.x.chart.call(chart.x.axis.chart);
    chart.chart.axis.x.zoom.call(chart.x.axis.zoom);
    chart.chart.axis.y.chart.call(chart.y.axis.chart);
    chart.chart.axis.y.zoom.call(chart.y.axis.zoom);
    fix_y_axis_labels(chart);

    if (chart.data_model == "timeseries") {
	set_x_axis_timeseries_label(chart);
    }

    if (chart.stacked) {
	chart.chart.plot = chart.chart.container.selectAll(".plot")
	    .data(chart.datasets.valid)
	    .enter().append("g")
	    .classed("plot", true);

	chart.chart.plot.append("path")
	    .classed("area", function(d) { d.dom.path = d3.select(this); return true; })
	    .attr("d", function(d) { if (d.values === undefined) { return null; } return chart.functions.area(d.values); })
	    .style("fill", function(d) { return mycolors(d.index); })
	    .classed("hidden", function(d) { if (d.hidden) { return true; } else { return false; }; })
	    .attr("clip-path", "url(#clip_" + chart.charts_index + ")");

	for (var i=0; i<chart.datasets.valid.length; i++) {
	    if (chart.datasets.valid[i].values.length > 1) {
		continue;
	    }

	    chart.datasets.valid[i].dom.points = d3.select(chart.datasets.valid[i].dom.path[0][0].parentNode).selectAll(".points")
		.data(chart.datasets.valid[i].values)
		.enter().append("line")
		.classed("points", true)
		.attr("r", 3)
		.attr("clip-path", "url(#clip_" + chart.charts_index + ")")
		.style("stroke", mycolors(chart.datasets.valid[i].index))
		.classed("hidden", function(d) { if (d.hidden) { return true; } else { return false; }; })
		.attr("x1", get_chart_scaled_x)
		.attr("x2", get_chart_scaled_x)
		.attr("y1", get_chart_scaled_y0)
		.attr("y2", get_chart_scaled_y_y0);
	}
    } else {
	chart.chart.plot = chart.chart.container.selectAll(".plot")
	    .data(chart.datasets.valid)
	    .enter().append("g")
	    .classed("plot", true);

	chart.chart.plot.append("path")
	    .classed("line", function(d) { d.dom.path = d3.select(this); return true; })
	    .attr("d", function(d) { if (d.values === undefined) { return null; } return chart.functions.line(d.values); })
	    .style("stroke", function(d) { return mycolors(d.index) })
	    .classed("hidden", function(d) { if (d.hidden) { return true; } else { return false; }; })
	    .attr("clip-path", "url(#clip_" + chart.charts_index + ")");

	for (var i=0; i<chart.datasets.valid.length; i++) {
	    if (chart.datasets.valid[i].values.length > 1) {
		continue;
	    }

	    chart.datasets.valid[i].dom.points = d3.select(chart.datasets.valid[i].dom.path[0][0].parentNode).selectAll(".points")
		.data(chart.datasets.valid[i].values)
		.enter().append("circle")
		.classed("points", true)
		.attr("r", 3)
		.attr("clip-path", "url(#clip_" + chart.charts_index + ")")
		.style("fill", mycolors(chart.datasets.valid[i].index))
		.style("stroke", mycolors(chart.datasets.valid[i].index))
		.classed("hidden", function(d) { if (d.hidden) { return true; } else { return false; }; })
		.attr("cx", get_chart_scaled_x)
		.attr("cy", get_chart_scaled_y);
	}
    }

    chart.chart.cursor_points = chart.chart.container.append("g")
	.classed("cursor_points", true);

    for (var i=0; i<chart.datasets.valid.length; i++) {
	chart.datasets.valid[i].dom.cursor_point = chart.chart.cursor_points.selectAll(".cursor_points")
	    .data([ chart.datasets.valid[i].values[0] ])
	    .enter().append("circle")
	    .classed("value_points hidden", true)
	    .attr("r", 5)
	    .attr("clip-path", "url(#clip_" + chart.charts_index + ")")
	    .style("fill", mycolors(chart.datasets.valid[i].index))
	    .attr("cx", get_chart_scaled_x)
	    .attr("cy", get_chart_scaled_y_stack);
    }
}

function create_table(chart) {
    var colspan;

    if (chart.data_model == "histogram") {
	colspan = 12;
    } else {
	colspan = 5;
    }

    chart.dom.table.table = chart.dom.table.location.append("table")
	.classed("chart", true);

    chart.dom.table.table.append("tr")
	.classed("header", true)
	.append("th")
	.attr("colSpan", colspan)
	.text(chart.chart_title);

    var row = chart.dom.table.table.append("tr")
	.classed("header", true);

    var cell = row.append("th")
	.attr("colSpan", colspan)
	.text("Threshold: ");

    chart.dom.table.threshold = cell.append("input")
	.attr("type", "text")
	.property("value", function() {
	    if (chart.options.hide_dataset_threshold) {
		return chart.options.hide_dataset_threshold;
	    }
	});

    cell.selectAll(".apply_y_max")
	.data([ chart ])
	.enter().append("button")
	.text("Apply Max Y")
	.on("click", apply_y_max_threshold);

    cell.selectAll(".apply_y_average")
	.data([ chart ])
	.enter().append("button")
	.text("Apply Y Average")
	.on("click", apply_y_average_threshold);

    var row = chart.dom.table.table.append("tr")
	.classed("header", true);

    var cell = row.append("th")
	.attr("colSpan", colspan)
	.text("Dataset Name Filter: ");

    chart.dom.table.name_filter = cell.append("input")
	.attr("type", "text");

    cell.selectAll(".apply_name_filter_show")
	.data([ chart ])
	.enter().append("button")
	.text("Show Datasets")
	.on("click", apply_name_filter_show);

    cell.selectAll(".apply_name_filter_hide")
	.data([ chart ])
	.enter().append("button")
	.text("Hide Datasets")
	.on("click", apply_name_filter_hide);

    if (chart.options.live_update) {
	console.log("Creating table controls for chart \"" + chart.chart_title + "\"...");

	var row = chart.dom.table.table.append("tr")
	    .classed("header", true);

	var cell = row.append("th")
	    .attr("colSpan", colspan)
	    .text("History Length: ");

	chart.dom.table.live_update.history = cell.append("input")
	    .attr("type", "text")
	    .property("value", function() {
		if (chart.options.history_length) {
		    return chart.options.history_length;
		}
	    });

	cell.append("button")
	    .text("Update")
	    .on("click", function() {
		var value = chart.dom.table.live_update.history.property("value");
		if (!isNaN(value)) {
		    chart.options.history_length = value;
		} else if (chart.options.history_length) {
		    chart.dom.table.live_update.history.property("value", chart.options.history_length);
		}
	    });

	var row = chart.dom.table.table.append("tr")
	    .classed("header", true);

	var cell = row.append("th")
	    .attr("colSpan", colspan)
	    .text("Update Interval: ");

	chart.dom.table.live_update.interval = cell.append("input")
	    .attr("type", "text")
	    .property("value", function() {
		if (chart.options.update_interval) {
		    return chart.options.update_interval;
		}
	    });

	cell.append("button")
	    .text("Update")
	    .on("click", function() {
		var value = chart.dom.table.live_update.interval.property("value");
		if (!isNaN(value)) {
		    chart.options.update_interval = value;
		    if (chart.state.live_update) {
			//pause
			chart.chart.playpause.on("click")();
			//unpause
			chart.chart.playpause.on("click")();
		    }
		} else {
		    if (chart.options.update_interval) {
			chart.dom.table.live_update.interval.property("value", chart.options.update_interval);
		    }
		}
	    });

	console.log("...finished adding table controls for chart \"" + chart.chart_title + "\"");
    }

    var row = chart.dom.table.table.append("tr")
	.classed("header", true);

    row.append("th")
	.attr("align", "left")
	.text("Data Sets");

    row.append("th")
	.attr("align", "right")
	.text("Value");

    if (chart.data_model == "histogram") {
	row.append("th")
	    .attr("align", "right")
	    .text("Percentile");
    }

    row.append("th")
	.attr("align", "right")
	.text("Average");

    row.append("th")
	.attr("align", "right")
	.text("Median");

    if (chart.data_model == "histogram") {
	row.append("th")
	    .attr("align", "right")
	    .text("Min");

	row.append("th")
	    .attr("align", "right")
	    .text("Max");

	row.append("th")
	    .attr("align", "right")
	    .text("90%");

	row.append("th")
	    .attr("align", "right")
	    .text("95%");

	row.append("th")
	    .attr("align", "right")
	    .text("99%");

	row.append("th")
	    .attr("align", "right")
	    .text("99.99%");
    }

    row.append("th")
	.attr("align", "right")
	.text("Samples");

    for (var i=0; i<chart.datasets.all.length; i++) {
	chart.datasets.all[i].dom.table.row = chart.dom.table.table.selectAll(".tablerow")
	    .data([ chart.datasets.all[i] ])
	    .enter().append("tr")
	    .attr("id", "datarow")
	    .on("click", table_row_click)
	    .classed("invalidrow", chart.datasets.all[i].invalid)
	    .on("mouseover", mouseover_highlight_function)
	    .on("mouseout", mouseout_highlight_function);

	chart.datasets.all[i].dom.table.row.append("td")
	    .attr("align", "left")
	    .text(chart.datasets.all[i].name);

	chart.datasets.all[i].dom.table.value = chart.datasets.all[i].dom.table.row.append("td")
	    .attr("align", "right");

	if (chart.data_model == "histogram") {
	     chart.datasets.all[i].dom.table.percentile = chart.datasets.all[i].dom.table.row.append("td")
		.attr("align", "right");
	}

	chart.datasets.all[i].dom.table.mean = chart.datasets.all[i].dom.table.row.append("td")
	    .attr("align", "right")
	    .text(function() {
		if (chart.data_model == "histogram") {
		    return table_print(chart, chart.datasets.all[i].histogram.mean);
		} else {
		    return table_print(chart, chart.datasets.all[i].mean);
		}
	    });

	chart.datasets.all[i].dom.table.median = chart.datasets.all[i].dom.table.row.append("td")
	    .attr("align", "right")
	    .text(function() {
		if (chart.data_model == "histogram") {
		    return table_print(chart, chart.datasets.all[i].histogram.median);
		} else {
		    return table_print(chart, chart.datasets.all[i].median);
		}
	    });

	if (chart.data_model == "histogram") {
	    chart.datasets.all[i].dom.table.histogram.min = chart.datasets.all[i].dom.table.row.append("td")
		.attr("align", "right")
		.text(table_print(chart, chart.datasets.all[i].histogram.min));

	    chart.datasets.all[i].dom.table.histogram.max = chart.datasets.all[i].dom.table.row.append("td")
		.attr("align", "right")
		.text(table_print(chart, chart.datasets.all[i].histogram.max));

	    chart.datasets.all[i].dom.table.histogram.p90 = chart.datasets.all[i].dom.table.row.append("td")
		.attr("align", "right")
		.text(table_print(chart, chart.datasets.all[i].histogram.p90));

	    chart.datasets.all[i].dom.table.histogram.p95 = chart.datasets.all[i].dom.table.row.append("td")
		.attr("align", "right")
		.text(table_print(chart, chart.datasets.all[i].histogram.p95));

	    chart.datasets.all[i].dom.table.histogram.p99 = chart.datasets.all[i].dom.table.row.append("td")
		.attr("align", "right")
		.text(table_print(chart, chart.datasets.all[i].histogram.p99));

	    chart.datasets.all[i].dom.table.histogram.p9999 = chart.datasets.all[i].dom.table.row.append("td")
		.attr("align", "right")
		.text(table_print(chart, chart.datasets.all[i].histogram.p9999));
	}

	chart.datasets.all[i].dom.table.samples = chart.datasets.all[i].dom.table.row.append("td")
	    .attr("align", "right")
	    .text(function() {
		if (chart.data_model == "histogram") {
		    return chart.formatting.table.integer(chart.datasets.all[i].histogram.samples);
		} else {
		    return chart.formatting.table.integer(chart.datasets.all[i].values.length);
		}
	    });

	if (chart.datasets.all[i].hidden) {
	    chart.datasets.all[i].dom.table.row.classed("hiddenrow", true);
	}
    }

    chart.dom.table.data_rows = chart.dom.table.table.selectAll("#datarow");

    if (chart.stacked) {
	var row = chart.dom.table.table.append("tr")
	    .classed("footer", true);

	row.append("th")
	    .attr("align", "left")
	    .text("Combined Value");

	chart.dom.table.stacked.value = row.append("td")
	    .attr("align", "right");

	row.append("td");

	row.append("td");

	row.append("td");

	var row = chart.dom.table.table.append("tr")
	    .classed("footer", true);

	row.append("th")
	    .attr("align", "left")
	    .text("Combined Average");

	row.append("td");

	compute_stacked_mean(chart);

	chart.dom.table.stacked.mean = row.append("td")
	    .attr("align", "right")
	    .text(table_print(chart.table.stacked_mean));

	row.append("td");

	row.append("td");

	var row = chart.dom.table.table.append("tr")
	    .classed("footer", true);

	row.append("th")
	    .attr("align", "left")
	    .text("Combined Median");

	row.append("td");

	row.append("td");

	compute_stacked_median(chart);

	chart.dom.table.stacked.median = row.append("td")
	    .attr("align", "right")
	    .text(table_print(chart.table.stacked_median));

	row.append("td");
    }

    if (chart.options.raw_data_sources.length > 0) {
	var row = chart.dom.table.table.append("tr")
	    .classed("section", true);

	row.append("th")
	    .attr("align", "left")
	    .attr("colSpan", colspan)
	    .text("Raw Data Source(s):");

	var row = chart.dom.table.table.append("tr");

	var cell = row.append("td")
	    .attr("colSpan", colspan);

	for (var i=0; i<chart.options.raw_data_sources.length; i++) {
	    cell.append("a")
		.attr("href", chart.options.raw_data_sources[i])
		.text(chart.options.raw_data_sources[i].substr(chart.options.raw_data_sources[i].lastIndexOf("/") + 1))
		.append("br");
	}
    }
}

function update_y_axis_label(d, i) {
    var chart = this.ownerSVGElement.__data__;

    if ((this.getBBox().width + 10) >= chart.dimensions.margin.left) {
	var label = d3.select(this);
	label.on("mouseover", tooltip_on)
	    .on("mouseout", tooltip_off)
	    .attr("lengthAdjust", "spacingAndGlyphs")
	    .attr("textLength", chart.dimensions.margin.left - 10);
    }
}

function fix_y_axis_labels(chart) {
    chart.chart.axis.y.chart.selectAll("g.tick").selectAll("text").each(update_y_axis_label);
    chart.chart.axis.y.zoom.selectAll("g.tick").selectAll("text").each(update_y_axis_label);
}

function handle_brush_actions(chart) {
    if (chart.x.brush.empty()) {
	chart.x.brush.extent(chart.x.scale.chart.domain());
    }

    if (chart.y.brush.empty()) {
	chart.y.brush.extent(chart.y.scale.chart.domain());
    }

    var x_extent = chart.x.brush.extent();
    var y_extent = chart.y.brush.extent();

    var x_domain = chart.x.scale.zoom.domain();
    var y_domain = chart.y.scale.zoom.domain();

    chart.x.scale.chart.domain(x_extent);
    chart.y.scale.chart.domain(y_extent);

    chart.chart.axis.x.chart.call(chart.x.axis.chart);
    chart.chart.axis.y.chart.call(chart.y.axis.chart);

    chart.x.slider.call(chart.x.brush);
    chart.y.slider.call(chart.y.brush);

    update_dataset_chart_elements(chart);

    fix_y_axis_labels(chart);

    if (chart.data_model == "timeseries") {
	set_x_axis_timeseries_label(chart);
    }
}

function zoom_it(chart, zoom_factor) {
    var x_extent = chart.x.brush.extent();
    var x_domain = chart.x.scale.zoom.domain();

    if (chart.data_model == "timeseries") {
	// convert the timestamps into integers for the calculations that follow
	x_extent[0] = +x_extent[0];
	x_extent[1] = +x_extent[1];
	x_domain[0] = +x_domain[0];
	x_domain[1] = +x_domain[1];
    }
    var y_extent = chart.y.brush.extent();
    var y_domain = chart.y.scale.zoom.domain();

    var x_center = (x_extent[1] - x_extent[0]) / 2;
    var y_center = (y_extent[1] - y_extent[0]) / 2;

    x_extent[0] = x_extent[0] - (x_center * zoom_factor * chart.zoom_rate/100);
    x_extent[1] = x_extent[1] + (x_center * zoom_factor * chart.zoom_rate/100);

    y_extent[0] = y_extent[0] - (y_center * zoom_factor * chart.zoom_rate/100);
    y_extent[1] = y_extent[1] + (y_center * zoom_factor * chart.zoom_rate/100);

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

    if (chart.data_model == "timeseries") {
	// convert the integers back into date objects after the calculations are complete
	x_extent[0] = new Date(Math.floor(x_extent[0]));
	x_extent[1] = new Date(Math.ceil(x_extent[1]));
    }

    chart.x.scale.chart.domain(x_extent);
    chart.y.scale.chart.domain(y_extent);

    chart.x.brush.extent(x_extent);
    chart.y.brush.extent(y_extent);

    chart.chart.axis.x.chart.call(chart.x.axis.chart);
    chart.chart.axis.y.chart.call(chart.y.axis.chart);

    chart.chart.axis.x.zoom.call(chart.x.axis.zoom);
    chart.chart.axis.y.zoom.call(chart.y.axis.zoom);

    chart.x.slider.call(chart.x.brush);
    chart.y.slider.call(chart.y.brush);

    update_dataset_chart_elements(chart);

    fix_y_axis_labels(chart);

    if (chart.data_model == "timeseries") {
	set_x_axis_timeseries_label(chart);
    }
}
 
function generate_chart(stacked, data_model, location, chart_title, x_axis_title, y_axis_title, options, callback) {
    var charts_index = charts.push(new chart(charts, chart_title, stacked, data_model, x_axis_title, y_axis_title, location, options)) - 1;
    charts[charts_index].charts_index = charts_index;

    build_chart(charts[charts_index]);

    callback();
}

function build_chart(chart) {
    if ((chart.data_model == "xy") ||
	(chart.data_model == "timeseries") ||
	(chart.data_model == "histogram")) {
	console.log("User specified data_model=\"" + chart.data_model + "\" for chart \"" + chart.chart_title + "\"");
    } else {
	console.log("An unsupported data_model [\"" + chart.data_model + "\"] was specified for chart \"" + chart.chart_title + "\"");
	return;
    }

    console.log("Beginning to build chart \"" + chart.chart_title + "\"...");

    chart.dom.div = d3.select("#" + chart.location);

    if (chart.dom.div.empty()) {
	console.log("Failed to locate div for \"" + chart.chart_title + "\" identified by \"" + chart.location + "\"");
	return;
    }

    var table = chart.dom.div.append("table");

    var row = table.append("tr")
	.attr("vAlign", "top");

    var chart_cell = row.append("td");

    chart.dom.table.location = row.append("td");

    if (chart.options.x.scale.linear) {
	chart.x.scale.chart = d3.scale.linear();
	chart.x.scale.zoom = d3.scale.linear();
    } else if (chart.options.x.scale.time) {
	if (chart.options.timezone === "local") {
	    chart.x.scale.chart = d3.time.scale();
	    chart.x.scale.zoom = d3.time.scale();
	} else {
	    chart.options.timezone = "utc";
	    chart.x.scale.chart = d3.time.scale.utc();
	    chart.x.scale.zoom = d3.time.scale.utc();
	}
    } else if (chart.options.x.scale.log) {
	chart.x.scale.chart = d3.scale.log();
	chart.x.scale.zoom = d3.scale.log();
    }

    chart.x.scale.chart.range([0, chart.dimensions.viewport_width]);

    chart.x.scale.zoom.clamp(true)
	.range([0, chart.dimensions.viewport_width]);

    if (chart.options.y.scale.linear) {
	chart.y.scale.chart = d3.scale.linear();
	chart.y.scale.zoom = d3.scale.linear();
    } else if (chart.options.y.scale.log) {
	chart.y.scale.chart = d3.scale.log();
	chart.y.scale.zoom = d3.scale.log();
    }

    chart.y.scale.chart.range([chart.dimensions.viewport_height, 0]);

    chart.y.scale.zoom.clamp(true)
	.range([chart.dimensions.viewport_height, 0]);

    chart.x.axis.chart = d3.svg.axis()
	.scale(chart.x.scale.chart)
	.orient("bottom")
	.tickSize(-chart.dimensions.viewport_height);

    chart.x.axis.zoom = d3.svg.axis()
	.scale(chart.x.scale.zoom)
	.orient("top")
	.tickSize(9);

    if (chart.options.x.scale.time) {
	if (chart.options.timezone == "local") {
	    chart.x.axis.chart.tickFormat(chart.formatting.time.local.short);
	    chart.x.axis.zoom.tickFormat(chart.formatting.time.local.short);
	} else {
	    chart.x.axis.chart.tickFormat(chart.formatting.time.utc.short);
	    chart.x.axis.zoom.tickFormat(chart.formatting.time.utc.short);
	}
    }

    chart.x.brush = d3.svg.brush()
	.x(chart.x.scale.zoom);

    chart.y.axis.chart = d3.svg.axis()
	.scale(chart.y.scale.chart)
	.orient("left")
	.tickSize(-chart.dimensions.viewport_width);

    chart.y.axis.zoom = d3.svg.axis()
	.scale(chart.y.scale.zoom)
	.orient("right")
	.tickSize(9);

    chart.y.brush = d3.svg.brush()
	.y(chart.y.scale.zoom);

    if (chart.stacked) {
	chart.functions.area = d3.svg.area()
	    .x(get_chart_scaled_x)
	    .y0(get_chart_scaled_y0)
	    .y1(get_chart_scaled_y_y0);

	chart.functions.stack = d3.layout.stack()
	    .y(get_stack_layout_y)
	    .values(get_dataset_values);
    } else {
	chart.functions.line = d3.svg.line()
	    .x(get_chart_scaled_x)
	    .y(get_chart_scaled_y);
    }

    chart.chart.svg = chart_cell.selectAll(".svg")
	.data([chart])
	.enter().append("svg")
	.classed("svg", true)
	.attr("width", chart.dimensions.viewport_width + chart.dimensions.margin.left + chart.dimensions.margin.right)
	.attr("height", chart.dimensions.viewport_height + chart.dimensions.margin.top + chart.dimensions.margin.bottom + ((Math.ceil(chart.dataset_count / chart.dimensions.legend_properties.columns) - 1 + chart.options.legend_entries.length) * chart.dimensions.legend_properties.row_height));

    chart.chart.container = chart.chart.svg.append("g")
	.attr("transform", "translate(" + chart.dimensions.margin.left + ", " + chart.dimensions.margin.top +")");

    chart.chart.container.append("rect")
	.classed("titlebox", true)
	.attr("x", -chart.dimensions.margin.left)
	.attr("y", -chart.dimensions.margin.top)
	.attr("width", chart.dimensions.viewport_width + chart.dimensions.margin.left + chart.dimensions.margin.right + 2)
	.attr("height", 15);

    chart.chart.container.append("text")
	.classed("title middletext", true)
	.attr("x", (chart.dimensions.viewport_width/2))
	.attr("y", -chart.dimensions.margin.top + 11)
	.text(chart.chart_title);

    chart.chart.container.append("text")
	.classed("actionlabel endtext", true)
	.attr("x", chart.dimensions.viewport_width + chart.dimensions.margin.right - 10)
	.attr("y", -chart.dimensions.margin.top + 29)
	.on("click", function() {
		chart.x.scale.chart.domain(chart.x.scale.zoom.domain());
		chart.y.scale.chart.domain(chart.y.scale.zoom.domain());

		chart.x.brush.extent(chart.x.scale.zoom.domain());
		chart.y.brush.extent(chart.y.scale.zoom.domain());

		chart.chart.axis.x.chart.call(chart.x.axis.chart);
		chart.chart.axis.x.zoom.call(chart.x.axis.zoom);

		chart.chart.axis.y.chart.call(chart.y.axis.chart);
		chart.chart.axis.y.zoom.call(chart.y.axis.zoom);

		chart.x.slider.call(chart.x.brush);
		chart.y.slider.call(chart.y.brush);

		update_dataset_chart_elements(chart);

		fix_y_axis_labels(chart);

		if (chart.data_model == "timeseries") {
		    set_x_axis_timeseries_label(chart);
		}

		chart.state.user_x_zoomed = false;
		chart.state.user_y_zoomed = false;
	    })
	.text("Reset Zoom/Pan");

    chart.chart.container.append("text")
	.classed("actionlabel middletext", true)
	.attr("x", (-chart.dimensions.margin.left/2))
	.attr("y", (chart.dimensions.viewport_height + 30))
	.on("click", display_help)
	.text("Help");

    // make sure that the library was properly loaded prior to adding the "Save as PNG" link
    if (typeof saveSvgAsPng == 'function') {
	chart.chart.container.append("text")
	    .classed("actionlabel middletext", true)
	    .attr("x", (chart.dimensions.viewport_width / 4) * 2)
	    .attr("y", -chart.dimensions.margin.top + 29)
	    .on("click", function() {
		saveSvgAsPng(this.ownerSVGElement, chart.chart_title + ".png", {
		    backgroundColor: "#FFFFFF"
		});
	    })
	    .text("Save as PNG");
    }

    chart.chart.show_all = chart.chart.container.selectAll(".show")
	.data([ chart ])
	.enter().append("text")
	.classed("actionlabel middletext", true)
	.attr("x", (chart.dimensions.viewport_width / 4 * 3 - 40))
	.attr("y", -chart.dimensions.margin.top + 29)
	.text("Show");

    chart.chart.container.append("text")
	.classed("middletext", true)
	.attr("x", (chart.dimensions.viewport_width / 4 * 3 - 14))
	.attr("y", -chart.dimensions.margin.top + 29)
	.text("/");

    chart.chart.hide_all = chart.chart.container.selectAll(".hide")
	.data([ chart ])
	.enter().append("text")
	.classed("actionlabel middletext", true)
	.attr("x", (chart.dimensions.viewport_width / 4 * 3 + 11))
	.attr("y", -chart.dimensions.margin.top + 29)
	.text("Hide");

    chart.chart.container.append("text")
	.classed("middletext", true)
	.attr("x", (chart.dimensions.viewport_width / 4 * 3 + 43))
	.attr("y", -chart.dimensions.margin.top + 29)
	.text("All");

    chart.chart.container.append("text")
	.classed("actionlabel middletext", true)
	.attr("x", (chart.dimensions.viewport_width / 4))
	.attr("y", -chart.dimensions.margin.top + 29)
	.on("click", function() {
		var string = "\"" + chart.chart_title + "\"\n\"" + chart.x.axis.title.text + "\"";
		var x_values = [];
		for (var i=0; i<chart.datasets.all.length; i++) {
		    string = string + ",\"" + chart.datasets.all[i].name + " (" + chart.y.axis.title.text + ")\"";

		    // create a temporary placeholder for storing
		    // the next index to start searching at below
		    chart.datasets.all[i].tmp_index = 0;

		    for (var x=0; x<chart.datasets.all[i].values.length; x++) {
			x_values.push(chart.datasets.all[i].values[x].x);
		    }
		}
		string = string + "\n";

		x_values.sort(function(a, b) { return a - b; });

		var x_domain = chart.x.scale.chart.domain();

		for (var i=0; i<x_values.length; i++) {
		    // skip repeated x_values
		    if ((i > 0) && (x_values[i] == x_values[i-1])) {
			continue;
		    }

		    if ((x_values[i] >= x_domain[0]) &&
			(x_values[i] <= x_domain[1])) {
			string = string + x_values[i] + ",";

			for (var d=0; d<chart.datasets.all.length; d++) {
			    for (var b=chart.datasets.all[d].tmp_index; b<chart.datasets.all[d].values.length; b++) {
				if (chart.datasets.all[d].values[b].x == x_values[i]) {
				    string = string + chart.datasets.all[d].values[b].y;
				    // store the next index to start searching at
				    chart.datasets.all[d].tmp_index = b + 1;
				    break;
				}
			    }

			    string = string + ",";
			}

			string = string + "\n";
		    }
		}

		for (var d=0; d<chart.datasets.all.length; d++) {
		    delete chart.datasets.all[d].tmp_index;
		}

		create_download(chart.chart_title + '.csv', 'text/csv', 'utf-8', string);
	    })
	.text("Export Data as CSV");

    chart.chart.container.append("text")
	.classed("actionlabel middletext", true)
	.attr("x", (chart.dimensions.viewport_width - 10))
	.attr("y", (chart.dimensions.viewport_height + 30))
	.on("click", function() {
		var x_domain = chart.x.scale.chart.domain();

		for (var i=0; i<chart.charts.length; i++) {
		    if (chart.charts[i].chart.container == chart.chart.container) {
			// skip applying zoom to myself
			continue;
		    }

		    var target_domain = chart.charts[i].x.scale.zoom.domain();
		    var source_domain = chart.x.scale.zoom.domain();

		    var domain_check = 0;

		    if (chart.data_model == "timeseries") {
			if (chart.charts[i].data_model == "timeseries") {
			    if ((target_domain[0].getTime() !== source_domain[0].getTime()) ||
				(target_domain[1].getTime() !== source_domain[1].getTime())) {
				domain_check = 1;
			    }
			} else {
			    domain_check = 1;
			}
		    } else {
			if (chart.charts[i].data_model == "timeseries") {
			    domain_check = 1;
			} else {
			    if ((target_domain[0] !== source_domain[0]) ||
				(target_domain[1] !== source_domain[1])) {
				domain_check = 1;
			    }
			}
		    }

		    if (domain_check) {
			console.log("Skipping application of X-Axis zoom from \"" + chart.chart_title + "\" to \"" + chart.charts[i].chart_title + "\" because data domains are not a match");
			return;
		    }

		    chart.charts[i].x.scale.chart.domain(x_domain);

		    chart.charts[i].x.brush.extent(x_domain);

		    chart.charts[i].chart.axis.x.chart.call(chart.charts[i].x.axis.chart);

		    chart.charts[i].x.slider.call(chart.charts[i].x.brush);

		    update_dataset_chart_elements(chart.charts[i]);
		}
	    })
	.text("Apply X-Axis Zoom to All");

    chart.chart.axis.x.chart = chart.chart.container.append("g")
	.classed("axis", true)
	.attr("transform", "translate(0," + chart.dimensions.viewport_height +")")
	.call(chart.x.axis.chart);

    chart.x.axis.title.dom = chart.chart.axis.x.chart.append("text")
	.classed("bold middletext", true)
	.attr("y", 30)
	.attr("x", (chart.dimensions.viewport_width/2))
	.text(chart.x.axis.title.text);

    chart.chart.axis.x.zoom = chart.chart.container.append("g")
	.classed("axis", true)
	.attr("transform", "translate(0, -15)")
	.call(chart.x.axis.zoom);

    var x_arc = d3.svg.arc()
	.outerRadius(10)
	.startAngle(function(d, i) { if (i) { return Math.PI; } else { return 0; } })
	.endAngle(function(d, i) { if (i) { return 2 * Math.PI; } else { return Math.PI; } });

    chart.x.slider = chart.chart.container.append("g")
	.classed("slider", true)
	.call(chart.x.brush);

    chart.x.slider.selectAll(".resize").append("path")
	.attr("transform", "translate(0, -15)")
	.attr("d", x_arc);

    chart.x.slider.selectAll("rect")
	.attr("transform", "translate(0, -25)")
	.attr("height", 20);

    chart.chart.axis.y.chart = chart.chart.container.append("g")
	.classed("axis", true)
	.call(chart.y.axis.chart);

    chart.y.axis.title.dom = chart.chart.axis.y.chart.append("text")
	.classed("bold starttext", true)
	.attr("x", -chart.dimensions.margin.left + 10)
	.attr("y", -40)
	.text(chart.y.axis.title.text);

    chart.chart.axis.y.zoom = chart.chart.container.append("g")
	.classed("axis", true)
	.attr("transform", "translate(" + (chart.dimensions.viewport_width + 15) + ", 0)")
	.call(chart.y.axis.zoom);

    var y_arc = d3.svg.arc()
	.outerRadius(10)
	.startAngle(function(d, i) { if (i) { return 0.5 * Math.PI; } else { return -0.5 * Math.PI; } })
	.endAngle(function(d, i) { if (i) { return 1.5 * Math.PI; } else { return 0.5 * Math.PI; } });

    chart.y.slider = chart.chart.container.append("g")
	.classed("slider", true)
	.call(chart.y.brush);

    chart.y.slider.selectAll(".resize").append("path")
	.attr("transform", "translate(" + (chart.dimensions.viewport_width + 15) + ", 0)")
	.attr("d", y_arc);

    chart.y.slider.selectAll("rect")
	.attr("transform", "translate(" + (chart.dimensions.viewport_width + 5) + ", 0)")
	.attr("width", 20);

    chart.chart.show_all.on("click", show_all);
    chart.chart.hide_all.on("click", hide_all);

    chart.x.brush.on("brush", function() {
	    if (d3.event.sourceEvent == null) {
		chart.x.brush.extent(chart.x.scale.chart.domain());
		chart.x.slider.call(chart.x.brush);
		return;
	    }

	    handle_brush_actions(chart);

	    chart.state.user_x_zoomed = true;
	});

    chart.y.brush.on("brush", function() {
	    if (d3.event.sourceEvent == null) {
		chart.y.brush.extent(chart.y.scale.chart.domain());
		chart.y.slider.call(chart.y.brush);
		return;
	    }

	    handle_brush_actions(chart);

	    chart.state.user_y_zoomed = true;
	});

    var x_domain = chart.x.scale.chart.domain();
    var y_domain = chart.y.scale.chart.domain();

    chart.chart.container.append("clipPath")
	.attr("id", "clip_" + chart.charts_index)
	.append("rect")
	.attr("x", chart.x.scale.chart(x_domain[0]))
	.attr("y", chart.y.scale.chart(y_domain[1]))
	.attr("width", chart.x.scale.chart(x_domain[1]) - chart.x.scale.chart(x_domain[0]))
	.attr("height", chart.y.scale.chart(y_domain[0]) - chart.y.scale.chart(y_domain[1]));

    chart.chart.viewport = chart.chart.container.selectAll(".viewport")
	.data([ chart ])
	.enter().append("rect")
	.classed("pane", true)
	.attr("width", chart.dimensions.viewport_width)
	.attr("height", chart.dimensions.viewport_height)
	.on("mouseenter", viewport_mouseenter)
	.on("mousedown", viewport_mousedown)
	.on("mouseup", viewport_mouseup)
	.on("mouseout", viewport_mouseout)
	.on("mousemove", viewport_mousemove);

    chart.chart.loading = chart.chart.container.append("text")
	.classed("loadinglabel middletext", true)
	.attr("x", (chart.x.scale.chart(x_domain[1]) - chart.x.scale.chart(x_domain[0])) / 2)
	.attr("y", (chart.y.scale.chart(y_domain[0]) - chart.y.scale.chart(y_domain[1])) / 2 + 35)
	.text("Loading");

    if (chart.options.csvfiles) {
	// this path can have no parallelism since it is unknown how
	// many datasets each CSV file might contain
	chart.datasets_queue = d3.queue(1);

	for (var i=0; i<chart.options.csvfiles.length; i++) {
	    // add a dataset load to the queue
	    chart.datasets_queue.defer(load_csv_files, chart.options.csvfiles[i], chart);
	}
    } else {
	// this path can have some parallelism, but place a limit on
	// it to keep things under control
	chart.datasets_queue = d3.queue(512);

	if (chart.options.packed && chart.options.plotfile) {
	    // add a packed dataset load to the queue
	    chart.datasets_queue.defer(load_plot_file, chart.options.plotfile, chart);
	} else {
	    if (chart.options.plotfiles) {
		for (var i=0; i<chart.options.plotfiles.length; i++) {
		    // add a dataset load to the queue
		    chart.datasets_queue.defer(load_plot_files, chart.options.plotfiles[i], chart, i);
		}
	    } else {
		if (chart.options.json_plotfile) {
		    chart.datasets_queue.defer(load_json, chart);
		}
	    }
	}
    }

    // block waiting for the queue processing to complete before completing the chart
    chart.datasets_queue.await(function(error, results) {
	    chart.chart.loading.remove();
	    chart.chart.loading = null;

	    console.log("Content load complete for chart \"" + chart.chart_title + "\".");

	    if (chart.options.sort_datasets) {
		if (chart.data_model == "histogram") {
		    console.log("Sorting datasets descending by histogram mean for chart \"" + chart.chart_title + "\"...");
		    chart.datasets.all.sort(dataset_histogram_sort);
		} else {
		    console.log("Sorting datasets descending by mean for chart \"" + chart.chart_title + "\"...");
		    chart.datasets.all.sort(dataset_sort);
		}
		console.log("...finished sorting datasets for chart \"" + chart.chart_title + "\"...");

		// the dataset indexes need to be updated after sorting
		for (var i=0; i<chart.datasets.all.length; i++) {
		    chart.datasets.all[i].index = i;
		}
	    }

	    for (var i=0; i<chart.datasets.all.length; i++) {
		if (!chart.datasets.all[i].invalid) {
		    chart.datasets.valid.push(chart.datasets.all[i]);
		} else {
		    console.log("ERROR: Dataset \"" + chart.datasets.all[i].name + "\" for chart \"" + chart.chart_title + "\" is empty.  It has been flagged as invalid and many user actions will be ignored for this dataset.");
		}
	    }

	    if (chart.datasets.all.length > chart.dataset_count) {
		console.log("Resizing SVG for chart \"" + chart.chart_title + "\".");
		chart.chart.svg.attr("height", chart.dimensions.viewport_height + chart.dimensions.margin.top + chart.dimensions.margin.bottom + ((Math.ceil(chart.datasets.all.length / chart.dimensions.legend_properties.columns) - 1 + chart.options.legend_entries.length) * chart.dimensions.legend_properties.row_height))
	    }

	    console.log("Creating table for chart \"" + chart.chart_title + "\"...");
	    create_table(chart);
	    console.log("...finished adding table for chart \"" + chart.chart_title + "\"");

	    console.log("Processing datasets for chart \"" + chart.chart_title + "\"...");
	    complete_chart(chart);
	    console.log("...finished processing datasets for chart \"" + chart.chart_title + "\"");

	    chart.x.slider.call(chart.x.brush.event);
	    chart.y.slider.call(chart.y.brush.event);

	    chart.chart.zoomout = chart.chart.container.append("g")
		.classed("chartbutton", true)
		.classed("hidden", true)
		.on("click", function() {
			zoom_it(chart, 1);
			chart.state.user_x_zoomed = true;
			chart.state.user_y_zoomed = true;
		    })
		.on("mouseout", function() {
			chart.chart.viewport_controls.classed("hidden", true);
		    })
		.on("mouseover", function() {
			chart.chart.viewport_controls.classed("hidden", false);
		    });

	    chart.chart.zoomout.append("circle")
		.attr("cx", 20)
		.attr("cy", 20)
		.attr("r", 11);

	    chart.chart.zoomout.append("text")
		.classed("middletext", true)
		.attr("x", 20)
		.attr("y", 24)
		.text("-");

	    chart.chart.zoomin = chart.chart.container.append("g")
		.classed("chartbutton", true)
		.classed("hidden", true)
		.on("click", function() {
			zoom_it(chart, -1);
			chart.state.user_x_zoomed = true;
			chart.state.user_y_zoomed = true;
		    })
		.on("mouseout", function() {
			chart.chart.viewport_controls.classed("hidden", true);
		    })
		.on("mouseover", function() {
			chart.chart.viewport_controls.classed("hidden", false);
		    });

	    chart.chart.viewport_controls = d3.selectAll([chart.chart.zoomout.node(),
							  chart.chart.zoomin.node()]);

	    chart.chart.zoomin.append("circle")
		.attr("cx", 50)
		.attr("cy", 20)
		.attr("r", 11);

	    chart.chart.zoomin.append("text")
		.classed("middletext", true)
		.attr("x", 50)
		.attr("y", 24)
		.text("+");

	    chart.chart.xcursorline = chart.chart.container.append("line")
		.classed("cursorline hidden", true)
		.attr("x1", 0)
		.attr("y1", 0)
		.attr("x2", 1)
		.attr("y2", 1);

	    chart.chart.ycursorline = chart.chart.container.append("line")
		.classed("cursorline hidden", true)
		.attr("x1", 0)
		.attr("y1", 0)
		.attr("x2", 1)
		.attr("y2", 1);

	    chart.chart.coordinates = chart.chart.container.append("text")
		.classed("coordinates endtext hidden", true)
		.attr("x", chart.dimensions.viewport_width - 5)
		.attr("y", 15)
		.text("coordinates");

	    chart.chart.viewport_elements = d3.selectAll([chart.chart.xcursorline.node(),
							  chart.chart.ycursorline.node(),
							  chart.chart.coordinates.node()]);

	    console.log("...finished building chart \"" + chart.chart_title + "\"");

	    if (chart.options.live_update) {
		chart.interval = window.setInterval(function() {
		    live_update(chart);
		}, chart.options.update_interval * 1000);

		chart.chart.playpause = chart.chart.container.append("g")
		    .classed("chartbutton", true)
		    .classed("hidden", true)
		    .on("click", function() {
			if (chart.state.live_update) {
			    chart.state.live_update = false;
			    clearInterval(chart.interval);
			} else {
			    chart.state.live_update = true;
			    chart.interval = window.setInterval(function() {
				live_update(chart);
			    }, chart.options.update_interval * 1000);
			}
		    })
		    .on("mouseout", function() {
			chart.chart.viewport_controls.classed("hidden", true);
		    })
		    .on("mouseover", function() {
			chart.chart.viewport_controls.classed("hidden", false);
		    });

		chart.chart.viewport_controls = d3.selectAll([chart.chart.zoomout.node(),
							      chart.chart.zoomin.node(),
							      chart.chart.playpause.node()]);

		chart.chart.playpause.append("circle")
		    .attr("cx", 35)
		    .attr("cy", 45)
		    .attr("r", 11);

		chart.chart.playpause.append("polygon")
		    .classed("playicon", true)
		    .attr("points", "29,42 29,49 34,45");

		chart.chart.playpause.append("line")
		    .classed("pauseicon", true)
		    .attr("x1", 37)
		    .attr("y1", 41)
		    .attr("x2", 37)
		    .attr("y2", 50);

		chart.chart.playpause.append("line")
		    .classed("pauseicon", true)
		    .attr("x1", 41)
		    .attr("y1", 41)
		    .attr("x2", 41)
		    .attr("y2", 50);
	    }
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
	    d3.select("body").classed("completedpage", true);
	    console.log("Finished generating all charts");
	});
}

function click_highlight_function(dataset) {
    if (dataset.hidden || dataset.invalid) {
	return;
    }

    if ((dataset.chart.state.chart_selection == -1) ||
	(dataset.chart.state.chart_selection != dataset.index)) {
	if (dataset.chart.state.chart_selection != -1) {
	    dehighlight(dataset.chart.datasets.all[dataset.chart.state.chart_selection]);
	    dataset.chart.datasets.all[dataset.chart.state.chart_selection].highlighted = false;
	}
	dataset.highlighted = true;
	dataset.chart.state.chart_selection = dataset.index;
	highlight(dataset);
    } else {
	dataset.highlighted = false;
	dataset.chart.state.chart_selection = -1;
	dehighlight(dataset);
    }
}

function mouseover_highlight_function(dataset) {
    if (dataset.hidden || dataset.invalid) {
	return;
    }

    if (dataset.chart.state.chart_selection == -1) {
	highlight(dataset);
    }
}

function mouseout_highlight_function(dataset) {
    if (dataset.hidden || dataset.invalid) {
	return;
    }

    if (dataset.chart.state.chart_selection == -1) {
	dehighlight(dataset);
    }
}

function highlight(dataset) {
    if (dataset.invalid) {
	return;
    }

    dataset.dom.legend.label.classed("bold", true);

    if (dataset.chart.stacked) {
	for (var i = 0; i < dataset.chart.datasets.valid.length; i++) {
	    if (dataset.chart.datasets.valid[i].hidden) {
		continue;
	    }

	    if (dataset.chart.datasets.valid[i].index == dataset.index) {
		dataset.chart.datasets.valid[i].dom.path.classed("unhighlighted", false);

		if (dataset.chart.datasets.valid[i].dom.points) {
		    dataset.chart.datasets.valid[i].dom.points.classed({"unhighlighted": false, "highlightedpoint": true});
		}

	    } else {
		dataset.chart.datasets.valid[i].dom.path.classed("unhighlighted", true);

		if (dataset.chart.datasets.valid[i].dom.points) {
		    dataset.chart.datasets.valid[i].dom.points.classed({"unhighlighted": true, "highlightedpoint": false});
		}
	    }
	}
    } else {
	for (var i = 0; i < dataset.chart.datasets.valid.length; i++) {
	    if (dataset.chart.datasets.valid[i].hidden) {
		continue;
	    }

	    if (dataset.chart.datasets.valid[i].index == dataset.index) {
		dataset.chart.datasets.valid[i].dom.path.classed({"unhighlighted": false, "highlightedline": true });

		if (dataset.chart.datasets.valid[i].dom.points) {
		    dataset.chart.datasets.valid[i].dom.points.classed("unhighlighted", false)
			.attr("r", 4);
		}
	    } else {
		dataset.chart.datasets.valid[i].dom.path.classed({"unhighlighted": true, "highlightedline": false });

		if (dataset.chart.datasets.valid[i].dom.points) {
		    dataset.chart.datasets.valid[i].dom.points.classed("unhighlighted", true);
		}
	    }
	}
    }

    for (var i = 0; i < dataset.chart.datasets.valid.length; i++) {
	if (dataset.chart.datasets.valid[i].hidden) {
	    continue;
	}

	if (dataset.chart.datasets.valid[i].index == dataset.index) {
	    dataset.chart.datasets.valid[i].dom.legend.rect.classed("unhighlighted", false);
	} else {
	    dataset.chart.datasets.valid[i].dom.legend.rect.classed("unhighlighted", true);
	}
    }

    dataset.dom.table.row.classed("highlightedrow", true);
}

function dehighlight(dataset) {
    if (dataset.invalid) {
	return;
    }

    dataset.dom.legend.label.classed("bold", false);

    if (dataset.chart.stacked) {
	for (var i = 0; i < dataset.chart.datasets.valid.length; i++) {
	    if (dataset.chart.datasets.valid[i].hidden) {
		continue;
	    }

	    dataset.chart.datasets.valid[i].dom.path.classed("unhighlighted", false);

	    if (dataset.chart.datasets.valid[i].dom.points) {
		dataset.chart.datasets.valid[i].dom.points.classed({"unhighlighted": false, "highlightedpoint": false});
	    }
	}
    } else {
	for (var i = 0; i < dataset.chart.datasets.valid.length; i++) {
	    if (dataset.chart.datasets.valid[i].hidden) {
		continue;
	    }

	    dataset.chart.datasets.valid[i].dom.path.classed({"unhighlighted": false, "highlightedline": false});

	    if (dataset.chart.datasets.valid[i].dom.points) {
		dataset.chart.datasets.valid[i].dom.points.classed("unhighlighted", false)
		    .attr("r", 3);
	    }
	}
    }

    for (var i = 0; i < dataset.chart.datasets.valid.length; i++) {
	if (dataset.chart.datasets.valid[i].hidden) {
	    continue;
	}

	dataset.chart.datasets.valid[i].dom.legend.rect.classed("unhighlighted", false);
    }

    dataset.dom.table.row.classed("highlightedrow", false);
}

function tooltip_on(d, i) {
    var object = d3.select(this);
    var svg = d3.select(object[0][0].ownerSVGElement);
    var coordinates = d3.mouse(object[0][0].ownerSVGElement);
    var chart = object[0][0].ownerSVGElement.__data__;

    var string;

    // if d is an object (ex. legend label) then a reference to the
    // tooltip can be embedded in the object.  if d is a literal
    // (ex. axis label) then a reference to the tooltip must be
    // embedded in the element object where the tooltip_on event
    // originates
    if (typeof d != "object") {
	string = d;
	d = this;
    } else {
	string = d.name;
	d = d.dom;
    }

    if (!isNaN(string)) {
	string = chart.formatting.tooltip(string);
    }

    d.tooltip = svg.append("g");

    var text = d.tooltip.append("text")
	.classed("bold tooltip starttext", true)
	.attr("x", coordinates[0] + 20)
	.attr("y", coordinates[1] - 20)
	.text(string);

    var dimensions = text[0][0].getBBox();

    var tooltip_margin = 10;

    // check if the box will flow off the right side of the chart
    // before drawing it and update the location of the text if it
    // will
    if ((dimensions.x + dimensions.width + tooltip_margin) > chart.dimensions.total_width) {
	text.attr("x", dimensions.x + (chart.dimensions.total_width - (dimensions.x + dimensions.width + tooltip_margin + 5)));

	// update the dimensions since they have changed
	dimensions = text[0][0].getBBox();
    }

    // insert the box before the text so that the text appears on top
    // of it rather than below it
    d.tooltip.insert("rect", ".tooltip")
	.classed("bold tooltip", true)
	.attr("x", dimensions.x - tooltip_margin)
	.attr("y", dimensions.y - tooltip_margin)
	.attr("rx", 10)
	.attr("ry", 10)
	.attr("width", dimensions.width + 2 * tooltip_margin)
	.attr("height", dimensions.height + 2 * tooltip_margin);
}

function tooltip_off(d, i) {
    // if d is an object (ex. legend label) then a reference to the
    // tooltip can be obtained from the object.  if d is a literal
    // (ex. axis label) then a reference to the tooltip must be
    // obtained from the element object where the tooltip_off event
    // originates
    if (typeof d != "object") {
	d = this;
    } else {
	d = d.dom;
    }

    d.tooltip.remove();
    delete d.tooltip;
}

function set_x_axis_timeseries_label(chart) {
    var label = "Time ";

    var domain = chart.x.scale.chart.domain();

    if (chart.options.timezone == "local") {
	label += "(" + chart.formatting.timezone(domain[0]) + "): " + chart.formatting.time.local.long(domain[0]) + " - " + chart.formatting.time.local.long(domain[1]);
    } else {
	label += "(UTC/GMT): " + chart.formatting.time.utc.long(domain[0]) + " - " + chart.formatting.time.utc.long(domain[1]);
    }

    chart.x.axis.title.dom.text(label);
}

function show_all(chart) {
    var opacity;

    for (var i = 0; i < chart.datasets.valid.length; i++) {
	if (chart.datasets.valid[i].hidden) {
	    chart.datasets.valid[i].hidden = false;
	    chart.state.visible_datasets++;
	    chart.datasets.valid[i].dom.path.classed("hidden", false);
	    if (chart.datasets.valid[i].dom.points) {
		chart.datasets.valid[i].dom.points.classed("hidden", false);
	    }
	    chart.datasets.valid[i].dom.legend.rect.classed("invisible", false);
	    chart.datasets.valid[i].dom.table.row.classed("hiddenrow", false);
	}
    }

    if (chart.state.chart_selection != -1) {
	highlight(chart.datasets.all[chart.state.chart_selection]);
    }

    update_chart(chart);

    sort_table(chart);
}

function hide_all(chart) {
    if (chart.state.chart_selection != -1) {
	click_highlight_function(chart.datasets.all[chart.state.chart_selection]);
    }

    for (var i = 0; i < chart.datasets.valid.length; i++) {
	if (! chart.datasets.valid[i].hidden) {
	    chart.datasets.valid[i].hidden = true;
	    chart.datasets.valid[i].dom.path.classed("hidden", true);
	    if (chart.datasets.valid[i].dom.points) {
		chart.datasets.valid[i].dom.points.classed("hidden", true);
	    }
	    chart.datasets.valid[i].dom.legend.rect.classed("invisible", true);
	    chart.datasets.valid[i].dom.table.row.classed("hiddenrow", true);
	}
    }

    chart.state.visible_datasets = 0;

    sort_table(chart);
}

function toggle_hide_click_event(dataset) {
    toggle_hide(dataset, false, false);
}

function toggle_hide(dataset, skip_update_chart, skip_update_mouse) {
    if (dataset.invalid) {
	return;
    }

    if (dataset.hidden) {
	dataset.hidden = false;
	dataset.dom.path.classed("hidden", false);
	if (dataset.dom.points) {
	    dataset.dom.points.classed("hidden", false);
	}
	dataset.dom.legend.rect.classed("invisible", false);
	dataset.dom.table.row.classed("hiddenrow", false);
	dataset.chart.state.visible_datasets++;

	if (dataset.chart.state.chart_selection != -1) {
	    dataset.dom.legend.rect.classed("unhighlighted", true);
	    dataset.dom.path.classed("unhighlighted", true);
	} else {
	    dataset.dom.legend.rect.classed("unhighlighted", false);
	}
    } else {
	if ((dataset.chart.state.chart_selection != -1) &&
	    (dataset.chart.state.chart_selection == dataset.index)) {
	    dataset.chart.state.chart_selection = -1;
	    dehighlight(dataset);
	}

	// if this call is coming from a mouse action on the table we need to act accordingly
	if (!skip_update_mouse) {
	    // once this dataset is marked as hidden it will not be
	    // capable of executing it's mouseout function so call it
	    // manually
	    mouseout_highlight_function(dataset);
	}

	dataset.hidden = true;
	dataset.dom.path.classed("hidden", true);
	if (dataset.dom.points) {
	    dataset.dom.points.classed("hidden", true);
	}
	dataset.dom.legend.rect.classed("invisible", true);
	dataset.dom.table.row.classed("hiddenrow", true);
	dataset.chart.state.visible_datasets--;
    }

    // check if we are being told to defer this update
    if (!skip_update_chart) {
	update_chart(dataset.chart);

	sort_table(dataset.chart);
    }
}

function update_threshold_hidden_datasets(chart, field) {
    for (var i=0; i < chart.datasets.valid.length; i++) {
	var hidden = false;

	if (field == "max_y") {
	    if (chart.datasets.valid[i].max_y_value < chart.options.hide_dataset_threshold) {
		hidden = true;
	    }
	} else if (field == "mean") {
	    if (chart.data_model == "histogram") {
		if (chart.datasets.valid[i].histogram.mean < chart.options.hide_dataset_threshold) {
		    hidden = true;
		}
	    } else {
		if (chart.datasets.valid[i].mean < chart.options.hide_dataset_threshold) {
		    hidden = true;
		}
	    }
	}

	if (chart.datasets.valid[i].hidden != hidden) {
	    // since toggle_hide is potentially called many times here defer the call to update_charts
	    // since toggle_hide is being called manually skip the mouse update
	    toggle_hide(chart.datasets.valid[i], true, true);
	}
    }

    // make the deferred call to update charts
    update_chart(chart);

    sort_table(chart);
}

function update_dataset_chart_elements(chart) {
    if (chart.stacked) {
	for (var i=0; i<chart.datasets.valid.length; i++) {
	    if (chart.datasets.valid[i].hidden) {
		continue;
	    }

	    chart.datasets.valid[i].dom.path.attr("d", get_dataset_area);

	    if (chart.datasets.valid[i].dom.points) {
		chart.datasets.valid[i].dom.points.attr("x1", get_chart_scaled_x)
		    .attr("x2", get_chart_scaled_x)
		    .attr("y1", get_chart_scaled_y0)
		    .attr("y2", get_chart_Scaled_y_y0);
	    }
	}
    } else {
	for (var i=0; i<chart.datasets.valid.length; i++) {
	    if (chart.datasets.valid[i].hidden) {
		continue;
	    }

	    chart.datasets.valid[i].dom.path.attr("d", get_dataset_line);

	    if (chart.datasets.valid[i].dom.points) {
		chart.datasets.valid[i].dom.points.attr("cx", get_chart_scaled_x)
		    .attr("cy", get_chart_scaled_y);
	    }
	}
    }
}

function table_print(chart, value) {
    if (value === null) {
	return "-";
    } else if (isFinite(value)) {
	return chart.formatting.table.float(value);
    } else {
	return value;
    }
}

function set_dataset_value(chart, dataset_index, values_index) {
    chart.datasets.valid[dataset_index].dom.table.value.text(chart.formatting.table.float(chart.datasets.valid[dataset_index].values[values_index].y));
    if (chart.data_model == "histogram") {
	chart.datasets.valid[dataset_index].dom.table.percentile.text(chart.formatting.table.float(chart.datasets.valid[dataset_index].values[values_index].percentile));
    }
    chart.datasets.valid[dataset_index].cursor_index = values_index;
    chart.table.stacked_value += chart.datasets.valid[dataset_index].values[values_index].y;
    chart.datasets.valid[dataset_index].dom.cursor_point.data([ chart.datasets.valid[dataset_index].values[values_index] ]);
    chart.datasets.valid[dataset_index].dom.cursor_point.attr("cx", get_chart_scaled_x)
    chart.datasets.valid[dataset_index].dom.cursor_point.attr("cy", get_chart_scaled_y_stack)
    chart.datasets.valid[dataset_index].dom.cursor_point.classed("hidden", false);
}

function set_stacked_value(chart, value) {
    chart.dom.table.stacked.value.text(value);
}

function show_dataset_values(chart, x_coordinate) {
    // assume the mouse is moving from left to right
    var forward_search = true;

    // check if there is a cached cursor_value that can be used to
    // predict what direction the search should go; by caching the
    // last value that was searched for and then searching in the
    // proper direction the number of iterations required to find the
    // next value can be reduced, possibly significantly
    if (chart.state.cursor_value) {
	if (chart.state.live_update && !d3.event) {
	    // when live_update is on and there is no mousemove event
	    // the search direction cannot be flipped despite the fact
	    // that the coordinates would say it can -- the
	    // coordinates are dynamically changing without a
	    // direction
	    ;
	} else if (x_coordinate < chart.state.cursor_value) {
	    // assume the mouse is moving from right to left
	    forward_search = false;
	}
    } else {
	//without a cached cursor_value to base the search direction
	//off, figure out if the coordinate is closer to the start or
	//end of the domain and hope that results in a quicker search

	var domain = chart.x.scale.zoom.domain();

	var up = x_coordinate - domain[0];
	var down = domain[1] - x_coordinate;

	if (down < up) {
	    forward_search = false;
	}
    }

    // populate the cursor_value cache
    chart.state.cursor_value = x_coordinate;

    chart.table.stacked_value = 0;

    var set = false;
    var loop = true;
    var index = 0;

    for (var i=0; i<chart.datasets.valid.length; i++) {
	if (chart.datasets.valid[i].hidden) {
	    continue;
	}

	// if a dataset has only one value that value is always current
	if (chart.datasets.valid[i].values.length == 1) {
	    if (!chart.datasets.valid[i].cursor_index) {
		set_dataset_value(chart, i, 0);
	    }
	    continue;
	}

	set = false;
	loop = true;

	// check for a cached index value where the search should
	// start for the dataset
	if (chart.datasets.valid[i].cursor_index) {
	    index = chart.datasets.valid[i].cursor_index;
	} else {
	    // without a cached index value the search will start at
	    // the beginning of the array if doing a forward search or
	    // at the end of the array when doing a backward search
	    if (forward_search) {
		index = 0;
	    } else {
		index = chart.datasets.valid[i].values.length - 1;
	    }
	}

	while (loop) {
	    if (index == 0) {
		if ((chart.datasets.valid[i].values[index].x + chart.datasets.valid[i].values[index + 1].x)/2 >= x_coordinate) {
		    set = true;
		}
	    } else if (index == (chart.datasets.valid[i].values.length - 1)) {
		if ((chart.datasets.valid[i].values[index - 1].x + chart.datasets.valid[i].values[index].x)/2 <= x_coordinate) {
		    set = true;
		}
	    } else if (((chart.datasets.valid[i].values[index - 1].x + chart.datasets.valid[i].values[index].x)/2 <= x_coordinate) &&
		((chart.datasets.valid[i].values[index].x + chart.datasets.valid[i].values[index + 1].x)/2 >= x_coordinate)) {
		set = true;
	    }

	    if (set) {
		set_dataset_value(chart, i, index);
		loop = false;
	    } else if (forward_search) {
		index++;

		if (index >= (chart.datasets.valid[i].length - 1)) {
		    set_dataset_value(chart, i, chart.datasets.valid[i].length - 1);
		    loop = false;
		}
	    } else {
		index--;

		if (index <= 0) {
		    set_dataset_value(chart, i, 0);
		    loop = false
		}
	    }
	}
    }

    if (chart.stacked) {
	set_stacked_value(chart, chart.formatting.table.float(chart.table.stacked_value));
    }
}

function clear_dataset_values(chart) {
    // clear the cursor_value cache
    chart.state.cursor_value = null;

    for (var i=0; i<chart.datasets.valid.length; i++) {
	if (chart.datasets.valid[i].hidden) {
	    continue;
	}

	chart.datasets.valid[i].dom.table.value.text("");
	if (chart.data_model == "histogram") {
	    chart.datasets.valid[i].dom.table.percentile.text("");
	}
	chart.datasets.valid[i].dom.cursor_point.classed("hidden", true);

	// clear the dataset index cache
	chart.datasets.valid[i].cursor_index = null;
    }

    if (chart.stacked) {
	set_stacked_value(chart, "");
	chart.table.stacked_value = 0;
    }
}

function get_datapoint_x(datapoint) {
    return datapoint.x;
}

function get_datapoint_y(datapoint) {
    if (datapoint.y_backup === undefined) {
	return datapoint.y;
    } else {
	return datapoint.y_backup;
    }
}

function get_datapoint_y0(datapoint) {
    return datapoint.y0;
}

function get_datapoint_y_y0(datapoint) {
    return get_datapoint_y(datapoint) + datapoint.y0;
}

function get_dataset_min_x(dataset) {
    if (dataset.invalid || dataset.hidden || (dataset.values === undefined)) {
	return null;
    }

    return d3.min(dataset.values, get_datapoint_x);
}

function get_dataset_max_x(dataset) {
    if (dataset.invalid || dataset.hidden || (dataset.values === undefined)) {
	return null;
    }

    return d3.max(dataset.values, get_datapoint_x);
}

function get_dataset_min_y(dataset) {
    if (dataset.invalid || dataset.hidden || (dataset.values === undefined)) {
	return null;
    }

    return d3.min(dataset.values, get_datapoint_y);
}

function get_dataset_max_y(dataset) {
    if (dataset.invalid || dataset.hidden || (dataset.values === undefined)) {
	return null;
    }

    return d3.max(dataset.values, get_datapoint_y);
}

function get_dataset_min_y_stack(dataset) {
    if (dataset.invalid || dataset.hidden || (dataset.values === undefined)) {
	return null;
    }

    return d3.min(dataset.values, get_datapoint_y0);
}

function get_dataset_max_y_stack(dataset) {
    if (dataset.invalid || dataset.hidden || (dataset.values === undefined)) {
	return null;
    }

    return d3.max(dataset.values, get_datapoint_y_y0);
}

function get_chart_scaled_x(datapoint) {
    return datapoint.dataset.chart.x.scale.chart(datapoint.x);
}

function get_chart_scaled_y(datapoint) {
    return datapoint.dataset.chart.y.scale.chart(get_datapoint_y(datapoint));
}

function get_chart_scaled_y0(datapoint) {
    return datapoint.dataset.chart.y.scale.chart(datapoint.y0);
}

function get_chart_scaled_y_y0(datapoint) {
    return datapoint.dataset.chart.y.scale.chart(get_datapoint_y(datapoint) + datapoint.y0);
}

function get_chart_scaled_y_stack(datapoint) {
    if (datapoint.dataset.chart.stacked) {
	return get_chart_scaled_y_y0(datapoint);
    } else {
	return get_chart_scaled_y(datapoint);
    }
}

function get_dataset_area(dataset) {
    return dataset.chart.functions.area(dataset.values);
}

function get_dataset_line(dataset) {
    return dataset.chart.functions.line(dataset.values);
}

// the stack layout will munge the datapoint.y value when it is
// computing the stack (it is adjusted by the sum of all datasets
// lower in the stack), we need to preserve the original value for
// future stack calculations and other references so a custom accessor
// is implemented here that manages a backup of the datapoint.y value
// when the stack layout is called; we also have to fool the stack
// layout into understanding hidden datasets by telling it they have a
// datapoint.y value of 0
function get_stack_layout_y(datapoint) {
     if (!datapoint.dataset.hidden) {
	 if (datapoint.y_backup !== undefined) {
	     datapoint.y = datapoint.y_backup;
	     delete datapoint.y_backup;
	 }
	 return datapoint.y;
     } else {
	 if (datapoint.y_backup === undefined) {
	     datapoint.y_backup = datapoint.y;
	 }
	 return 0;
     }
}

function get_dataset_values(dataset) {
    return dataset.values;
}

function viewport_mouseenter(chart) {
    chart.chart.viewport_controls.classed("hidden", false);
    chart.chart.viewport_elements.classed("hidden", false);
}

function viewport_mousemove(chart) {
    var mouse;

    // check if there is a current mouseover event
    // otherwise use the coordinates that are cached from
    // a previous event; there is no current event when
    // the mousemove is called programmatically rather
    // than from an actual mousemove event (assumes that
    // without an actual mousemove event that the cursor
    // is still in the same location); the event may be
    // the wrong type if mousemove is programmatically
    // called while another event is active (such as
    // mouseup)
    if (d3.event && (d3.event.type == "mousemove")) {
	mouse = d3.mouse(this);
	chart.state.mouse = mouse;
    } else {
	mouse = chart.state.mouse;
    }

    var mouse_values = [ chart.x.scale.chart.invert(mouse[0]), chart.y.scale.chart.invert(mouse[1]) ];

    if (chart.data_model == "timeseries") {
	if (chart.options.timezone == "local") {
	    chart.chart.coordinates.text("x:" + chart.formatting.time.local.long(mouse_values[0]) +
					 " y:" + chart.formatting.table.float(mouse_values[1]));
	} else {
	    chart.chart.coordinates.text("x:" + chart.formatting.time.utc.long(mouse_values[0]) +
					 " y:" + chart.formatting.table.float(mouse_values[1]));
	}
    } else {
	chart.chart.coordinates.text("x:" + chart.formatting.table.float(mouse_values[0]) +
				     " y:" + chart.formatting.table.float(mouse_values[1]));
    }

    var domain = chart.y.scale.chart.domain();

    chart.chart.xcursorline.attr("x1", mouse[0])
	.attr("x2", mouse[0])
	.attr("y1", chart.y.scale.chart(domain[1]))
	.attr("y2", chart.y.scale.chart(domain[0]));

    domain = chart.x.scale.chart.domain();

    chart.chart.ycursorline.attr("x1", chart.x.scale.chart(domain[0]))
	.attr("x2", chart.x.scale.chart(domain[1]))
	.attr("y1", mouse[1])
	.attr("y2", mouse[1]);

    if (chart.chart.selection && (chart.chart.selection.size() == 1)) {
	var selection_x, selection_y,
	selection_width, selection_height;

	if (chart.state.selection_start[0] < mouse[0]) {
	    selection_x = chart.state.selection_start[0];
	    selection_width = mouse[0] - chart.state.selection_start[0];
	} else {
	    selection_x = mouse[0];
	    selection_width = chart.state.selection_start[0] - mouse[0];
	}

	if (chart.state.selection_start[1] < mouse[1]) {
	    selection_y = chart.state.selection_start[1];
	    selection_height = mouse[1] - chart.state.selection_start[1];
	} else {
	    selection_y = mouse[1];
	    selection_height = chart.state.selection_start[1] - mouse[1];
	}

	chart.chart.selection.attr("x", selection_x)
	    .attr("y", selection_y)
	    .attr("width", selection_width)
	    .attr("height", selection_height)
	    .classed("hidden", false);
    }

    show_dataset_values(chart, mouse_values[0]);
}

function viewport_mouseout(chart) {
    chart.chart.viewport_controls.classed("hidden", true);
    chart.chart.viewport_elements.classed("hidden", true);
    if (chart.chart.selection) {
	chart.chart.selection.remove();
	chart.chart.selection = null;
    }
    chart.state.selection_active = false;

    clear_dataset_values(chart);

    chart.state.mouse = null;
}

function viewport_mousedown(chart) {
    if (d3.event.button != 0) {
	return;
    }

    chart.state.selection_start = d3.mouse(this);

    if (chart.chart.selection) {
	chart.chart.selection.remove();
	chart.chart.selection = null;
    }

    chart.chart.selection = chart.chart.container.insert("rect", "#coordinates")
	.classed("selection hidden", true)
	.attr("x", 0)
	.attr("y", 0)
	.attr("width", 1)
	.attr("height", 1);

    chart.state.selection_active = true;
}

function viewport_mouseup(chart) {
    if ((d3.event.button != 0) ||
	!chart.state.selection_active) {
	return;
    }

    chart.state.selection_stop = d3.mouse(this);

    chart.chart.selection.remove();
    chart.chart.selection = null;

    chart.state.selection_active = false;

    if ((chart.state.selection_start[0] == chart.state.selection_stop[0]) ||
	(chart.state.selection_start[1] == chart.state.selection_stop[1])) {
	return;
    }

    var x_extent = Array(0, 0), y_extent = Array(0, 0);

    if (chart.state.selection_start[0] < chart.state.selection_stop[0]) {
	x_extent[0] = chart.x.scale.chart.invert(chart.state.selection_start[0]);
	x_extent[1] = chart.x.scale.chart.invert(chart.state.selection_stop[0]);
    } else {
	x_extent[0] = chart.x.scale.chart.invert(chart.state.selection_stop[0]);
	x_extent[1] = chart.x.scale.chart.invert(chart.state.selection_start[0]);
    }

    if (chart.state.selection_start[1] < chart.state.selection_stop[1]) {
	y_extent[1] = chart.y.scale.chart.invert(chart.state.selection_start[1]);
	y_extent[0] = chart.y.scale.chart.invert(chart.state.selection_stop[1]);
    } else {
	y_extent[1] = chart.y.scale.chart.invert(chart.state.selection_stop[1]);
	y_extent[0] = chart.y.scale.chart.invert(chart.state.selection_start[1]);
    }

    chart.x.brush.extent(x_extent);
    chart.y.brush.extent(y_extent);

    chart.x.scale.chart.domain(x_extent);
    chart.y.scale.chart.domain(y_extent);

    chart.chart.axis.x.chart.call(chart.x.axis.chart);
    chart.chart.axis.y.chart.call(chart.y.axis.chart);

    chart.x.slider.call(chart.x.brush);
    chart.y.slider.call(chart.y.brush);

    update_dataset_chart_elements(chart);

    fix_y_axis_labels(chart);

    if (chart.data_model == "timeseries") {
	set_x_axis_timeseries_label(chart);
    }

    chart.state.user_x_zoomed = true;
    chart.state.user_y_zoomed = true;

    // after the mouseup event has been handled a
    // mousemove event needs to be programmatically
    // initiated to update for the new zoom state
    chart.chart.viewport.on("mousemove")(chart);
}

function table_row_click(dataset) {
    if (dataset.invalid) {
	return;
    }

    if (dataset.hidden) {
	toggle_hide(dataset, false, false);
	mouseover_highlight_function(dataset);
    } else {
	click_highlight_function(dataset);
    }
}

function apply_y_max_threshold(chart) {
    var value = chart.dom.table.threshold.property("value");

    if (!isNaN(value)) {
	chart.options.hide_dataset_threshold = value;

	update_threshold_hidden_datasets(chart, "max_y");
    } else if (chart.options.hide_dataset_threshold) {
	chart.dom.table.threshold.property("value", chart.options.hide_dataset_threshold);
    } else {
	chart.dom.table.threshold.property("value", "");
    }
}

function apply_y_average_threshold(chart) {
    var value = chart.dom.table.threshold.property("value");

    if (!isNaN(value)) {
	chart.options.hide_dataset_threshold = value;

	update_threshold_hidden_datasets(chart, "mean");
    } else if (chart.options.hide_dataset_threshold) {
	chart.dom.table.threshold.property("value", chart.options.hide_dataset_threshold);
    } else {
	chart.dom.table.threshold.property("value", "");
    }
}

function apply_name_filter_show(chart) {
    var regex = new RegExp(chart.dom.table.name_filter.property("value"));

    for (var i=0; i<chart.datasets.valid.length; i++) {
	var hidden = true;

	if (regex.test(chart.datasets.valid[i].name)) {
	    hidden = false;
	}

	if (chart.datasets.valid[i].hidden != hidden) {
	    // since toggle_hide is potentially called many times here defer the call to update_charts
	    // since toggle_hide is being called manually skip the mouse update
	    toggle_hide(chart.datasets.valid[i], true, true);
	}
    }

    // make the deferred call to update charts
    update_chart(chart);

    sort_table(chart);
}

function apply_name_filter_hide(chart) {
    var regex = new RegExp(chart.dom.table.name_filter.property("value"));

    for (var i=0; i<chart.datasets.valid.length; i++) {
	var hidden = false;

	if (regex.test(chart.datasets.valid[i].name)) {
	    hidden = true;
	}

	if (chart.datasets.valid[i].hidden != hidden) {
	    // since toggle_hide is potentially called many times here defer the call to update_charts
	    // since toggle_hide is being called manually skip the mouse update
	    toggle_hide(chart.datasets.valid[i], true, true);
	}
    }

    // make the deferred call to update charts
    update_chart(chart);

    sort_table(chart);
}

function sort_table(chart) {
    if (chart.options.sort_datasets) {
	chart.dom.table.data_rows.sort(datarow_sort);
    }
}

function datarow_sort(a, b) {
    if (!a.invalid && b.invalid) {
	return 1;
    } else if (a.invalid && !b.invalid) {
	return -1;
    } else if (a.invalid && b.invalid) {
	return 0;
    } else if (!a.hidden && b.hidden) {
	return -1;
    } else if (a.hidden && !b.hidden) {
	return 1;
    } else {
	if (a.chart.data_model == "histogram") {
	    return b.histogram.mean - a.histogram.mean;
	} else {
	    return b.mean - a.mean;
	}
    }
}

function dataset_sort(a, b) {
    if (!a.invalid && b.invalid) {
	return 1;
    } else if (a.invalid && !b.invalid) {
	return -1;
    } else if (a.invalid && b.invalid) {
	return 0;
    } else {
	return b.mean - a.mean;
    }
}

function dataset_histogram_sort(a, b) {
    if (!a.invalid && b.invalid) {
	return 1;
    } else if (a.invalid && !b.invalid) {
	return -1;
    } else if (a.invalid && b.invalid) {
	return 0;
    } else {
	return b.histogram.mean - a.histogram.mean;
    }
}

function display_help() {
    var help = "This chart provides interactive features to assist the user in interpreting the data.\n\n";
    help += "You can \"lock\" a dataset to be hightlighted by clicking it's text in the legend or it's row in the table to the right of the chart.  Click either to \"unlock\" the selection.\n\n";
    help += "You can show or hide all datasets using the \"Show\" or \"Hide\" buttons at the top of the chart area.  Individual datasets can be hidden or unhidden by clicking the legend icon for that dataset.  A hidden dataset can also be unhidden by clicking it's table row.\n\n";
    help += "When moving your mouse around the chart area, the coordinates will be displayed in the upper right part of the chart area.\n\n";
    help += "You can zoom into a selected area by clicking in the chart area and dragging the cursor to the opposite corner of the rectangular area you would like to focus on.  When you release the cursor the selection will be zoomed.\n\n";
    help += "You can also zoom in/out using the +/- controls which are visible when the mouse is over the chart area.\n\n";
    help += "You can control the panning and/or zooming using the slider controls above and to the right of the chart area.\n\n";
    help += "You can apply any x-axis zooming to all charts on the page by clicking the \"Apply X-Axis Zoom to All\" button (as long as the x-axis domains match).\n\n";
    help += "To reset the chart area to it's original state after being panned/zoomed, hit the \"Reset Zoom/Pan\" button in the upper right.\n\n";
    help += "You can download a CSV file for the data by clicking the \"Export Data as CSV\" button located under the chart title.  The exported data is limited by x-axis zooming, if performed.\n\n";
    help += "Datasets highlighted in yellow in the table have been marked as invalid due to a problem while loading.  These datasets are permanently hidden and will ignore many user initiated events.\n\n";
    help += "When the page has completed generating all charts, the background will change colors to signal that loading is complete.\n";

    alert(help);
}
