var semver = require('semver');

var max = exports.max = function (versions) {
  return versions.sort(semver.rcompare)[0];
};

var min = exports.min = function (versions) {
  return versions.sort(semver.compare)[0];
};

exports.gt = function (v, versions) {
  var m = max(versions);
  return semver.gt(v, m);
};

exports.lt = function (v, versions) {
  var m = min(versions);
  return semver.lt(v, m);
};

exports.unique = function (v, versions) {
  return versions.indexOf(v) < 0;
};