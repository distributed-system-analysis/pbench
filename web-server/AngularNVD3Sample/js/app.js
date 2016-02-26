var app = angular.module('sample', ['nvd3']);

app.controller('graphControl', function ($scope, $http) {
    $scope.options = {
        chart: {
            type: 'lineWithFocusChart',
            height: 450,
            width: 500,
            focusHeight: 50,
            interactive: true,
            showLegend: true,
            useInteractiveGuideline: true,
            forceX: null,
            forceY: null,
            lines2: {
                forceX: null,
                forceY: null
            },
            margin: {
                top: 20,
                right: 20,
                bottom: 60,
                left: 40
            },
            transitionDuration: 500,
            x: function (d) {
                return d[0];
            },
            y: function (d) {
                return d[1];
            },
            xAxis: {
                axisLabel: 'X Axis',
                tickFormat: function (d) {
                    return d3.format(',f')(d);
                }
            },
            x2Axis: {
                tickFormat: function (d) {
                    return d3.format(',f')(d);
                }
            },
            yAxis: {
                axisLabel: 'Y Axis',
                tickFormat: function (d) {
                    return d3.format(',.2f')(d);
                },
                rotateYLabel: false
            },
            y2Axis: {
                tickFormat: function (d) {
                    return d3.format(',.2f')(d);
                }
            }

        }
    };
    $scope.data = null;
});

function constructChart(graph_type, chartnum, chart_file_name, threshold) {
    var chartid = "chart" + chartnum;
    d3.csv("csv/" + chart_file_name + ".csv", function (error, csv_data) {
        if (error) return console.log("there was an error loading the csv data from " + chart_file_name + ": " + error);
        if (csv_data.length == 0) return console.log("No data found for " + chart_file_name);

        var chart_datum = _process_csv_data(csv_data, threshold);
        if (chart_datum === undefined) return undefined;
        if (chart_datum.length == 0) return undefined;

        var start = chart_datum[0].values[0][0];
        var end = start;
        for (var i = 0; i < chart_datum.length; i++) {
            for (var j = 0; j < chart_datum[i].values.length; j++) {
                tval = chart_datum[i].values[j][0];
                if (tval < start) start = tval;
                if (tval > end) end = tval;
            }
        }
        
        var scope = angular.element(document.getElementById(chartid)).scope();
        scope.$apply(function () {
            scope.data = chart_datum;
        });
        
        d3.select(saveid).on("click", function() {
            saveSvgAsPng($("#chart1 nvd3 svg")[0], chart_file_name + ".png");
        });
    });
};

function fetchData() {
    constructChart("lineWithFocusChart", 1, "cpu_all_cpu_busy");
};

function _process_csv_data(csv_data, threshold) {
    // This code assumes the .csv format is in one of two forms:
    //   1. ts, m0, m1, m2, ..., mN
    //   2. ts0, m0, ts1, m1, ts2, m2, ..., tsN, mN
    // And it also assumes that the label for each timestamp column is
    // "timestamp_ms", no matter how many are present

    var keys = Object.keys(csv_data[0]);

    if (keys.length <= 1) return console.log("No viable data to graph for " + chart_file_name);
    if (!keys[0].startsWith("timestamp_") && !keys[0].endsWith("_ms")) {
        return console.log("Unrecognized .csv data file format for " + chart_file_name);
    }

    // We first transform the data into a hash table, below we make a slight
    // adjustment to put it into the array form nv.d3 expects.
    var _chart_datum = {};
    var k, i, key, val;

    for (k = 0; k < keys.length; k++) {
        key = keys[k];
        if (key.startsWith("timestamp_") && key.endsWith("_ms")) continue;
        _chart_datum[key] = [];
    }

    if (keys.length >= 4 && keys[2].startsWith("timestamp_") && keys[2].endsWith("_ms")) {
        if (keys.length % 2 != 0) return console.log("Even number of columns expected for metrics with their own timestamps for " + chart_file_name);
        // Assume: ts0, m0, ts1, m1, ts2, m2, ..., tsN, mN
        for (i = 1; i < csv_data.length; i++) {
            for (k = 1; k < keys.length; k += 2) {
                key = keys[k];
                if (key.startsWith("timestamp_") && key.endsWith("_ms")) return console.log("Bug! " + chart_file_name);
                val = csv_data[i][key];
                if (val == "") continue;
                _chart_datum[key].push([+csv_data[i]["timestamp_" + key + "_ms"], +val]);
            }
        }
    } else {
        // Assume: ts, m0, m1, m2, ..., mN
        for (i = 1; i < csv_data.length; i++) {
            for (k = 0; k < keys.length; k++) {
                key = keys[k];
                if (key == "timestamp_ms") continue;
                val = csv_data[i][key];
                if (val == "") continue;
                _chart_datum[key].push([+csv_data[i]["timestamp_ms"], +val]);
            }
        }
    }

    // Now we transform it into what nv.d3 expects.
    var chart_datum = [];
    for (k = 0; k < keys.length; k++) {
        key = keys[k];
        if (key.startsWith("timestamp_") && key.endsWith("_ms")) continue;
        if (_chart_datum[key].length == 0) continue;
        chart_datum.push({
            "key": key,
            "values": _chart_datum[key]
        });
    }
    return chart_datum;
};

$(function () {
    $(".dropdown").click(function () {
        $(".wrapper").slideToggle();
    });
});