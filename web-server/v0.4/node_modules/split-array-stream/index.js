'use strict';

var async = require('async');
var ended = require('is-stream-ended');

module.exports = function (array, stream, callback) {
  var arr = [].slice.call(array);

  async.whilst(
    function () {
      return !ended(stream) && arr.length > 0;
    },

    function (next) {
      stream.push(arr.shift());
      setImmediate(next);
    },

    function () {
      callback(ended(stream));
    });
};
