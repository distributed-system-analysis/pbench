var qs = require('qs');
var url = require('url');

module.exports = function () {
  return function (req, res, next) {
    var parsedUrl = url.parse(req.url);
    req.query = qs.parse(parsedUrl.query);
    next();
  };
};