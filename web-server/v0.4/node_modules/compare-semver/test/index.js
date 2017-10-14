var compare = require('../');
var test = require('tape');
var versions = [
  '0.0.11',
  '0.1.0',
  '0.2.0',
  '0.1.11'
];

test('gets the max value in list', function (t) {
  t.equal(compare.max(versions), '0.2.0', '0.2.0 is max semver version');
  t.end();
});

test('compares a single semver is greater than the list of versions', function (t) {
  t.ok(compare.gt('0.7.0', versions), '0.7.0 is the greatest');
  t.ok(compare.gt('1.0.0', versions), '1.0.0 is the greatest');
  t.notOk(compare.gt('0.1.0', versions), '0.1.0 is not greatest');
  t.end();
});

test('gets the min value in list', function (t) {
  t.equal(compare.min(versions), '0.0.11', '0.0.11 is min semver version');
  t.end();
});

test('compares a single semver is less than the list of versions', function (t) {
  t.ok(compare.lt('0.0.1', versions), '0.0.1 is the least');
  t.ok(compare.lt('0.0.0', versions), '0.0.0 is the least');
  t.notOk(compare.gt('0.1.0', versions), '0.1.0 is not the least');
  t.end();
});

test('version is unique compared to list of versions', function (t) {
  t.ok(compare.unique('0.1.1', versions), '0.1.1 is unique');
  t.notOk(compare.unique('0.1.0', versions), '0.1.0 is not unique');
  t.end();
});