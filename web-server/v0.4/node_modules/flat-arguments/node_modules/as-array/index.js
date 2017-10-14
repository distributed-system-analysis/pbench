var isArgs = require('lodash.isarguments');
var isObject = require('lodash.isobject');
var values = require('lodash.values');

module.exports = function (data, convertObject) {
  
  if (!data) {
    data = [];
  }
  
  if (isArgs(data)) {
    data = [].splice.call(data, 0);
  }
  
  if (isObject(data) && convertObject) {
    data = values(data);
  }
  
  return Array.isArray(data)
    ? data
    : [data];
};