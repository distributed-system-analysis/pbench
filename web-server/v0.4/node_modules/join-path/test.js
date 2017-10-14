var test = require('tape');

var join = require('./index.js');

test('joins a system path', function (t) {

  t.equal(join('some', 'path'), 'some/path', 'basic path');
  t.equal(join('/', 'some', 'path'), '/some/path', 'path with leading slash');
  t.equal(join('some', undefined, 'path'), 'some/path', 'path with undefined value');

  t.end();
});

test('joins a url', function (t) {

  t.equal(join('http://test.com/', '/about'), 'http://test.com/about', 'basic url');
  t.equal(join('http://', 'test.com', '/some/path'), 'http://test.com/some/path', 'http:// leading protocol only');
  t.equal(join('https://', 'test.com', '/some/path'), 'https://test.com/some/path', 'https:// leading protocol only');
  t.equal(join('ftp://', 'test.com', '/some/path'), 'ftp://test.com/some/path', 'ftp:// leading protocol only');

  t.end();
});

test('joins a url without only tld', function (t) {
  t.equal(join('http://test:3002/api/v1', '/some/path'), 'http://test:3002/api/v1/some/path', 'tld only with port');
  t.end();
});
