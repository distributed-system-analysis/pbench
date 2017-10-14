3.0.4 / 2016-05-24
==================

 * ensure compatibility with newer node version

3.0.3 / 2015-11-26
==================

 * tweak readme

3.0.2 / 2015-11-25
==================

 * fixes longstanding issue #14

3.0.1 / 2015-11-25
==================

 * fixes #17

3.0.0 / 2015-11-01
==================

 * drop node 0.10 support, add node 4 support
 * use `through2` internally
 * deprecate `parser.lineNo` and `parser.body`

2.0.0 / 2015-02-15
==================

 * iconv-lite should be used seperatly.
 * iojs and 0.12 compat.

1.0.0 / 2014-03-30
==================

 * No changes, I just want to start doing semver properly.

0.9.1 / 2014-03-25
==================

 * add simple CLI tool

0.9.0 / 2013-12-27
==================

 * fix #9
 * fix #8

0.8.1 / 2013-11-21
==================

 * fix: correctly parse empty quoted cells (#6)
 * update csv-spectrum devDep

0.8.0 / 2013-11-16
==================

 * change: use csv-spectrum as a node module and comply to its changed tests

0.7.0 / 2013-11-14
==================

 * change: use iconv-lite for encoding conversion (please test und submit issues)

0.6.1 / 2013-11-13
==================

 * fix: properly handle CRLF in quoted sequences

0.6.0 / 2013-11-12
==================

 * feature: add support for columns
 * fix: some small changes regarding quotes to align output with csv-spectrum
 * internal: implement _flush

0.5.1 / 2013-11-10
==================

 * fix: last line wasn't parsed (damn! please update!)

0.5.0 / 2013-07-19
==================

 * change: rename 'encoding' to 'inputEncoding'
 * fix: parsing of CRLF files (thanks ktk for reporting)
