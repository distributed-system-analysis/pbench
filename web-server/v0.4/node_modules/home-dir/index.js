var path = require('path');

var exports = module.exports = function (subDir) {
  var baseDir = process.env[(process.platform == 'win32') ? 'USERPROFILE' : 'HOME'];
  return (subDir) ? path.join(baseDir, subDir) : baseDir;
};

exports.directory = exports();
