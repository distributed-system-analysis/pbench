var asArray = require('../');
var test = require('tape');

test('returns the array passed in', function (t) {
  var arr = [1,2,3];
  t.deepEqual(asArray(arr), [1,2,3], 'returned array');
  t.end();
});

test('converts single item into array', function (t) {
  var fn = function () {};
  t.deepEqual(asArray(fn), [fn], 'returned array');
  t.end();
});

test('returns empty array with undefined passed in', function (t) {
  t.deepEqual(asArray(), [], 'empty array');
  t.end();
});

test('converts arguments variable with numbers into array', function (t) {
  function tester () {
    t.deepEqual(asArray(arguments), [1,2], 'converted to array');
    t.end();
  };
  
  tester(1, 2);
});

test('converts arguments variable with strings into array', function (t) {
  function tester () {
    t.deepEqual(asArray(arguments), ['arg1', 'arg2'], 'converted to array');
    t.end();
  };
  
  tester('arg1', 'arg2');
});

