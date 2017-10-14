csv-streamify [![Build Status](https://travis-ci.org/klaemo/csv-stream.svg?branch=master)](https://travis-ci.org/klaemo/csv-stream)
===
[![NPM](https://nodei.co/npm/csv-streamify.png?downloadRank=true)](https://nodei.co/npm/csv-streamify/)

Parses csv files. Accepts options. No coffee script, no weird APIs. Just streams. Tested against [csv-spectrum](https://github.com/maxogden/csv-spectrum) and used in production.
It is also "fast enough" (around 60,000 rows per second, but that varies with data obviously).

Works in node `0.12`, `4`, `5` and `6`. Might work in node `0.10`, but is not tested in it.

## Installation

```
npm install csv-streamify
```

## Usage

This module implements a simple node [stream.Transform](http://nodejs.org/api/stream.html#stream_class_stream_transform) stream.
You can write to it, read from it and use `.pipe` as you would expect.

```javascript
const csv = require('csv-streamify')
const fs = require('fs')

const parser = csv()

// emits each line as a buffer or as a string representing an array of fields
parser.on('data', function (line) {
  console.log(line)
})

// now pipe some data into it
fs.createReadStream('/path/to/file.csv').pipe(parser)
```

### with options and callback

The first argument can either be an options object (see below) or a callback function.

__Note:__ If you pass a callback to `csv-streamify` it will buffer the parsed data for you and
pass it to the callback when it's done. This behaviour can obviously lead to out of memory errors with very large csv files.

```javascript
const csv = require('csv-streamify')
const fs = require('fs')

const parser = csv({ objectMode: true }, function (err, result) {
  if (err) throw err
  // our csv has been parsed succesfully
  result.forEach(function (line) { console.log(line) })
})

// now pipe some data into it
fs.createReadStream('/path/to/file.csv').pipe(parser)
```

### Options

You can pass some options to the parser. **All of them are optional**.

The options are also passed to the underlying transform stream, so you can pass in any standard node core stream options.

```javascript
{
  delimiter: ',', // comma, semicolon, whatever
  newline: '\n', // newline character (use \r\n for CRLF files)
  quote: '"', // what's considered a quote
  empty: '', // empty fields are replaced by this,

  // if true, emit arrays instead of stringified arrays or buffers
  objectMode: false,

  // if set to true, uses first row as keys -> [ { column1: value1, column2: value2 }, ...]
  columns: false
}
```

Also, take a look at [iconv-lite](https://github.com/ashtuchkin/iconv-lite) (`npm install iconv-lite --save`), it provides pure javascript streaming character encoding conversion.

## CLI

To use on the command line install it globally:

```bash
$ npm install csv-streamify -g
```

This should add the `csv-streamify` command to your `$PATH`.

Then, you either pipe data into it or give it a filename:

```bash
# pipe data in
$ cat some_data.csv | csv-streamify
# pass a filename
$ csv-streamify some_data.csv > output.json
# tell csv-streamify to read from + wait on stdin
$ csv-streamify -
```

## Wishlist

- browser support
- better CLI

If you would like to contribute either of those just open an issue so we can discuss it further. :)

## Contributors

[Nicolas Hery](https://github.com/nicolashery) (objectMode)
