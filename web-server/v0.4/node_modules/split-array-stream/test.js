'use strict';

var assert = require('assert');
var through = require('through2');

var split = require('./index.js');

describe('split-array-stream', function () {
  var array = [
    { id: 1, user: 'Dave' },
    { id: 2, user: 'Dave' },
    { id: 3, user: 'Dave' },
    { id: 4, user: 'Stephen' }
  ];

  it('should work', function (done) {
    var numDataEvents = 0;

    var stream = through.obj();

    stream.on('data', function () { numDataEvents++; });

    split(array, stream, function (streamEnded) {
      assert.strictEqual(streamEnded, false);
      assert.strictEqual(numDataEvents, array.length);

      done();
    });
  });

  it('should not push more results after end', function (done) {
    var stream = through.obj();

    var numDataEvents = 0;
    var expectedNumDataEvents = 2;

    stream.on('data', function () {
      numDataEvents++;

      if (numDataEvents === expectedNumDataEvents) {
        this.end();
      }

      if (numDataEvents > expectedNumDataEvents) {
        throw new Error('Should not have received this event.');
      }
    });

    split(array, stream, function (streamEnded) {
      assert.strictEqual(streamEnded, true);
      assert.strictEqual(numDataEvents, expectedNumDataEvents);

      done();
    });
  });

  it('should not modify original array', function (done) {
    var expectedArray = [].slice.call(array);

    split(array, through.obj(), function () {
      assert.deepEqual(array, expectedArray);
      done();
    });
  });
});