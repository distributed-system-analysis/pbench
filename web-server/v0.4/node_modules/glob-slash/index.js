var path = require('path');

var exports = module.exports = slashGlob;
exports.normalize = normalize;

function slashGlob (value) {
    
  if (value.charAt(0) === '!') {
    return '!' + exports.normalize(value.substr(1));
  }
  
  return exports.normalize(value);
};

function normalize (value) {
  
  return path.normalize(path.join('/', value));
};