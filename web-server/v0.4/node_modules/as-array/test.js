var asArray = require('./index.js');
var namespace = require('tessed').namespace;
var test = namespace('as array');

test('returns the array passed in', function (assert) {

  var arr = [1,2,3];
  assert.deepEqual(asArray(arr), [1,2,3], 'returned array');
});

test('converts single item into array', function (assert) {

  var fn = function () {};
  assert.deepEqual(asArray(fn), [fn], 'returned array');
});

test('returns empty array with undefined passed in', function (assert) {

  assert.deepEqual(asArray(), [], 'empty array');
});

test('converts arguments variable with numbers into array', function (assert) {

  return function (end) {

    function tester () {
      assert.deepEqual(asArray(arguments), [1,2], 'converted to array');
      end();
    };

    tester(1, 2);
  };
});

test('converts arguments variable with strings into array', function (assert) {

  return function (end) {

    function tester () {
      assert.deepEqual(asArray(arguments), ['arg1', 'arg2'], 'converted to array');
      end();
    };

    tester('arg1', 'arg2');
  };
});

test('pulls the values from an object as the array', function (assert) {

  var dataArr = asArray({'0': 'value1', '1': 'value2'}, true);
  assert.deepEqual(dataArr, ['value1', 'value2'], 'values as array');
});

