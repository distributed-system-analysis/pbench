'use strict';

var assert = require('assert');
var through = require('through2');

var isStreamEnded = require('./index.js');

describe('is-stream-ended', function () {
  it('should return the correct ended state', function () {
    var stream = through();
    assert.strictEqual(isStreamEnded(stream), false);

    stream.end();
    assert.strictEqual(isStreamEnded(stream), true);
  });

  it('should work with a provided state', function () {
    var stream = through();
    assert.strictEqual(isStreamEnded(stream._writableState), false);

    stream.end();
    assert.strictEqual(isStreamEnded(stream._writableState), true);
  });
});
