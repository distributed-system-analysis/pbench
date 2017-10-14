var toxic = require('toxic');
var globSlash = require('glob-slash');
var isObject = require('lodash.isobject');

module.exports = function globSlasher (spec, options) {
  
  options = options || {};
  
  if (!spec || typeof spec === 'function') {
    return spec;
  }
  
  // Arrays
  if (Array.isArray(spec)) {
    return spec.map(defaultMutator);
  }
  
  // Strings or numbers
  if (!isObject(spec)) {
    return globSlash(spec.toString());
  }
  
  // Objects
  return toxic(spec, {
    mutator: function (value) {
      
      if (options.value === false || !isValidValueType(value)) {
        return value;
      }
      
      return globSlash(value);
    },
    keyMutator: function (key) {
      
      if (options.key === false) {
        return key;
      }
      
      return globSlash(key);
    }
  });
};

function defaultMutator (value) {
  
  if (typeof value !== 'string') {
    return value;
  }
  
  return globSlash(value);
}

function isValidValueType (value) {
  return value
    && !Array.isArray(value)
    && typeof value !== 'object'
    && typeof value !== 'function'
}