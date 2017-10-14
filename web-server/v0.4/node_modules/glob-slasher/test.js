var slasher = require('./index');
var test = require('tape');

test('prefixes the path that does not already have a slash', function (t) {
  
  t.equal(slasher('pathname'), '/pathname', 'added slash');
  t.equal(slasher(123), '/123', 'added slash to number');
  t.end();
});

test('does not add a leading slash to a path that already has a leading slash', function (t) {
  
  t.equal(slasher('/pathname'), '/pathname', 'no slash added');
  t.end();
});

test('adds leading slash to object with no options', function (t) {
  
  var obj = { key: 'value' };
  t.deepEqual(slasher(obj), {'/key': '/value'}, 'added slash to all items');
  t.end();
});

test('adds leading slash to object for only value or key', function (t) {
  
  var obj = {key: 'value'};
  t.deepEqual(slasher(obj, {key: false}), {key: '/value'}, 'added slash to value only');
  t.deepEqual(slasher(obj, {value: false}), {'/key': 'value'}, 'added slash to key only');
  t.end();
});

test('returns the same data if it is an invalid data type', function (t) {
  
  var fn = function () {};
  t.equal(slasher(fn).toString(), fn.toString(), 'returned same function');
  t.end();
});

test('does not add slashes to nested objects as values, only to the keys', function (t) {
  
  var obj = {
    key: {
      sub: 'value'
    }
  };
  
  t.deepEqual(slasher(obj), {'/key': { sub: 'value'}}, 'skip nested objects');
  t.end();
});

test('prefixes with slash when glob uses negation', function (t) {
  
  var obj = { '!**/something': 'value' };
  t.deepEqual(slasher(obj), {'!/**/something': '/value'}, 'added slash');
  t.end();
});

test('prefixes globs in an array', function (t) {
  
  var obj = ['!**/something', '**'];
  t.deepEqual(slasher(obj), ['!/**/something', '/**'], 'added slash');
  t.end();
});
