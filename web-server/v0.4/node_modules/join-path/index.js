var path = require('path');

var urlJoin = require('url-join');
var asArray = require('as-array');
var validUrl = require('valid-url');

var exports = module.exports = function () {

  var paths = asArray(arguments).map(replaceUndefined);

  return validUrl.isUri(paths[0])
    ? urlJoin.apply(urlJoin, paths)
    : path.join.apply(path, paths);
};

var isUrl = exports.isUrl = function (url) {

  return validUrl.isUri(url)
    || url === 'http://'
    || url === 'https://'
    || url === 'ftp://';
};

var replaceUndefined = exports.replaceUndefined = function (p, idx, paths) {

  return  (p === undefined || p === null)
    ? validUrl.isUri(paths[0]) ? '/' : path.sep
    : p;
}
