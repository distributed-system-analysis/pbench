var globSlash = require('./index');
var test = require('tape');

test('adds slash to beginning', function (t) {
  
  t.equal(globSlash('someGlob/**'), '/someGlob/**', 'added slash');
  t.equal(globSlash('/someGlob/**'), '/someGlob/**', 'already had a slash');
  t.end();
});

test('normalizes', function (t) {
  
  t.equal(globSlash('//**'), '/**', 'removed slash at beginning');
  t.equal(globSlash('**//**'), '/**/**', 'removed slash in middle');
  t.equal(globSlash.normalize('**//**'), '/**/**', 'removed slash in middle with normalize method');
  t.end();
});

test('adds slash with negation', function (t) {
  
  t.equal(globSlash('!something/**'), '!/something/**', 'added slash to beginning with no slash yet');
  t.equal(globSlash('!/something/**'), '!/something/**', 'added slash to beginning with a slash already there');
  t.end();
});