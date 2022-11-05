var app = angular.module('sample', ['nvd3']);

app.controller('MainCtrl', function($scope,$http) {
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
                margin : {
                    top: 20,
                    right: 20,
                    bottom: 60,
                    left: 40
                },
                transitionDuration: 500,
                xAxis: {
                    axisLabel: 'X Axis',
                    tickFormat: function(d){
                        return d3.format(',f')(d);
                    }
                },
                x2Axis: {
                    tickFormat: function(d){
                        return d3.format(',f')(d);
                    }
                },
                yAxis: {
                    axisLabel: 'Y Axis',
                    tickFormat: function(d){
                        return d3.format(',.2f')(d);
                    },
                    rotateYLabel: false
                },
                y2Axis: {
                    tickFormat: function(d){
                        return d3.format(',.2f')(d);
                    }
                }

            }
        };

        /*$http.get('cpu_all_cpu_busy.json').success(function(data) {
           $scope.data = data;
        });*/
    
        $scope.data = constructChart("lineWithFocusChart", 0, "cpu_all_cpu_busy");

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
          }
          else {
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
            chart_datum.push({"key": key, "values": _chart_datum[key]});
          }

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

        function constructChart(graph_type, chartnum, chart_file_name, threshold) {
          d3.csv("csv/" + chart_file_name + ".csv", function (error, csv_data) {
            if (error) return console.log("there was an error loading the csv data from " + chart_file_name + ": " + error);
            if (csv_data.length == 0) return console.log("No data found for " + chart_file_name);

            var chart_datum = _process_csv_data(csv_data, threshold);
            if (chart_datum === undefined) return chart_datum;
            if (chart_datum.length == 0) return chart_datum;

            var start = chart_datum[0].values[0][0];
            var end = start;
            for (var i = 0; i < chart_datum.length; i++) {
              for (var j = 0; j < chart_datum[i].values.length; j++) {
                tval = chart_datum[i].values[j][0];
                if (tval < start) start = tval;
                if (tval > end) end = tval;
              }
            }
            start = new Date(start);
            end = new Date(end);
            var _chartnum = chartnum.toString();
            var chartid = "chart" + _chartnum;
            var saveid = "#save" + _chartnum;
            var thischart;
            nv.addGraph(function() {
              thischart = nv.models[graph_type]()
                  .xScale(d3.time.scale.utc())
                  .x(xAccessor)
                  .y(yAccessor)
                  .useInteractiveGuideline(true)
                  .color(keyColor);
              thischart.margin().left = 100;
              thischart.xAxis
                  .axisLabel('Time (UTC) - ' + xLegendFormat(start) + ' to ' + xLegendFormat(end))
                  .tickFormat(xTickFormat);
              thischart.yAxis
                  .tickFormat(yTickFormat);
              d3.select('#' + chartid)
                  .datum(chart_datum)
                  .call(thischart);
              var current_height = parseInt(d3.select('svg#' + chartid).style('height'), 10);
              document.getElementById(chartid).style.height = String(current_height + thischart.legend.height()) + 'px';
              nv.utils.windowSize(thischart.update('height'));

              nv.utils.windowResize(thischart.update);
              return thischart;
            });

            d3.select(saveid).on("click", function() {
              saveSvgAsPng(document.getElementById(chartid), chart_file_name + ".png");
            });
          });
        };

        /* Random Data Generator (took from nvd3.org) */
        function generateData() {
            return stream_layers(3,10+Math.random()*200,.1).map(function(data, i) {
                return {
                    key: 'Stream' + i,
                    values: data
                };
            });
        }

        function stream_layers(n, m, o) {
            if (arguments.length < 3) o = 0;
            function bump(a) {
                var x = 1 / (.1 + Math.random()),
                    y = 2 * Math.random() - .5,
                    z = 10 / (.1 + Math.random());
                for (var i = 0; i < m; i++) {
                    var w = (i / m - y) * z;
                    a[i] += x * Math.exp(-w * w);
                }
            }
            return d3.range(n).map(function() {
                var a = [], i;
                for (i = 0; i < m; i++) a[i] = o + o * Math.random();
                for (i = 0; i < 5; i++) bump(a);
                return a.map(stream_index);
            });
        }

        function stream_waves(n, m) {
            return d3.range(n).map(function(i) {
                return d3.range(m).map(function(j) {
                    var x = 20 * j / m - i / 3;
                    return 2 * x * Math.exp(-.5 * x);
                }).map(stream_index);
            });
        }

        function stream_index(d, i) {
            return {x: i, y: Math.max(0, d)};
        }
});
