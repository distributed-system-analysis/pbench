'use strict';

module.exports = function (methodName) {
  var initialArguments = [].slice.call(arguments, 1);

  return function (item) {
    if (typeof item[methodName] === 'function') {
      var invokedArguments = [].slice.call(arguments, 1);
      return item[methodName].apply(item, initialArguments.concat(invokedArguments));
    }
  };
};
