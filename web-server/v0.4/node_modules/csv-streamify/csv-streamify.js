'use strict'

var through = require('through2')

module.exports = function (opts, cb) {
  if (typeof opts === 'function') {
    cb = opts
    opts = {}
  }
  opts = opts || {}
  if (typeof cb === 'function') opts.cb = cb

  opts.delimiter = opts.delimiter || ','
  opts.newline = opts.newline || '\n'
  opts.quote = opts.quote || '"'
  opts.empty = opts.hasOwnProperty('empty') ? opts.empty : ''
  opts.objectMode = opts.objectMode || false
  opts.hasColumns = opts.columns || false

  // state
  var state = {
    body: [],
    lineNo: 0,
    _isQuoted: false,
    _prev: [],
    _newlineDetected: false,
    _line: [],
    _field: '',
    _columns: []
  }

  return createParser(opts, state).on('error', function (err) {
    if (opts.cb) cb(err)
  })
}

function createParser (opts, state) {
  function emitLine (parser) {
    state._line.push(state._field)
    var line = {}

    if (opts.hasColumns) {
      if (state.lineNo === 0) {
        state._columns = state._line
        state.lineNo += 1
        reset()
        return
      }
      state._columns.forEach(function (column, i) {
        line[column] = state._line[i]
      })
      state._line = line
    }

    // buffer
    if (opts.cb) state.body.push(state._line)

    // emit the parsed line as an array if in object mode
    // or as a stringified array (default)
    if (opts.objectMode) {
      parser.push(state._line)
    } else {
      parser.push(JSON.stringify(state._line) + '\n')
    }

    state.lineNo += 1

    // reset state
    reset()
  }

  function queue (char) {
    state._prev.unshift(char)
    while (state._prev.length > 3) state._prev.pop()
  }

  function reset () {
    state._prev = []
    state._field = ''
    state._line = []
    state._isQuoted = false
  }

  return through(opts, function parse (chunk, enc, cb) {
    var data = chunk.toString()
    var c

    for (var i = 0; i < data.length; i++) {
      c = data.charAt(i)

      // we have a line break
      if (!state._isQuoted && state._newlineDetected) {
        state._newlineDetected = false
        emitLine(this)
        // crlf
        if (c === opts.newline[1]) {
          queue(c)
          continue
        }
      }

      // are the last two chars quotes?
      if (state._isQuoted && state._prev[0] === opts.quote && state._prev[1] === opts.quote) {
        state._field += opts.quote
        state._prev = []
      }

      // skip over quote
      if (c === opts.quote) {
        queue(c)
        continue
      }

      // once we hit a regular char, check if quoting applies

      // xx"[c]
      if (c !== opts.quote && state._prev[0] === opts.quote &&
          state._prev[1] !== opts.quote) {
        state._isQuoted = !state._isQuoted
      }

      // """[c]
      if (c !== opts.quote && state._prev[0] === opts.quote &&
          state._prev[1] === opts.quote && state._prev[2] === opts.quote) {
        state._isQuoted = !state._isQuoted
        state._field += opts.quote
      }

      // x""[c]
      if (state._field && c !== opts.quote &&
          state._prev[0] === opts.quote &&
          state._prev[1] === opts.quote &&
          state._prev[2] !== opts.quote) {
        state._field += opts.quote
      }

      // delimiter
      if (!state._isQuoted && c === opts.delimiter) {
        if (state._field === '') state._field = opts.empty
        state._line.push(state._field)
        state._field = ''
        queue(c)
        continue
      }

      // newline
      if (!state._isQuoted && (c === opts.newline || c === opts.newline[0])) {
        state._newlineDetected = true
        queue(c)
        continue
      }

      queue(c)
      // append current char to _field string
      state._field += c
    }
    cb()
  }, function flush (fn) {
    // flush last line
    try {
      if (state._line.length || state._field) emitLine(this)
      if (opts.cb) opts.cb(null, state.body)
      fn()
    } catch (err) {
      fn(err)
    }
  })
}
