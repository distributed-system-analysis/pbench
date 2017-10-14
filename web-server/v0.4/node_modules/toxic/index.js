var _ = require('lodash');

module.exports = function (data, options) {
  
  options = _.extend({
    mutator: function (val) {
      return val;
    }
  }, options);
  
  if (typeof data !== 'object') {
    throw new Error('[toxic] requires an object to mutate');
  }
  
  return _(data)
    .map(function (value, key) {
      
      // Which mutator to use
      var keyMutator = options.keyMutator || options.mutator;
      var valueMutator = options.valueMutator || options.mutator;
      
      return [
        keyMutator(key),
        valueMutator(value)
      ];
    })
    .filter(_.identity)
    .zipObject()
    .value();
};
