/*jslint node: true, indent: 2, passfail: true */
"use strict";

var Table = require('cli-table');

function percentDifference(a, b) {
  return ((a - b) / ((a + b) / 2)) * 100;
}

function print() {
  var headers = ["Name", "Mean", "Variance", "% Error", "% Slower"],
    t = new Table({"head": headers}),
    precision = 5,
    results,
    fastest;

  results = this.filter('successful').map(function (item) {
    return {
      "name": item.name,
      "mean": item.stats.mean,
      "variance": item.stats.variance,
      "moe": item.stats.moe,
      "rme": item.stats.rme
    };
  }).sort(function (a, b) {
    return a.mean + a.moe > b.mean + b.moe;
  });

  fastest = results[0];
  results.forEach(function (item) {
    var diff = percentDifference(
      item.mean + item.moe,
      fastest.mean + fastest.moe
    );
    t.push([
      item.name,
      item.mean.toPrecision(precision),
      item.variance.toPrecision(precision),
      item.rme.toPrecision(precision) + ' %',
      diff.toPrecision(precision) + ' %'
    ]);
  });
  process.stdout.write("\n");
  process.stdout.write(String(this.name) + ":\n");
  process.stdout.write(t.toString());
  process.stdout.write("\n");
}

module.exports = print;
