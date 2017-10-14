var asArray = require('as-array');
var flatten = require('array-flatten');
var isArguments = require('lodash.isarguments');
var isObject = require('lodash.isobject');

var flattenArguments = function () {
  return flatten(argumentsToArray(arguments));
};

function argumentsToArray (args) {
  return asArray(args)
    .map(function (arg) {
      if (!isArguments(arg)) return arg;
      if (isObject(arg)) arg = argumentsToArray(arg);
      
      return asArray(arg);
    });
}

module.exports = flattenArguments;