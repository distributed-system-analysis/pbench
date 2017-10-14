'use strict';

var assert = require('assert')
var duplexify = require('duplexify')
var stream = require('stream')
var StreamEvents = require('./')
var util = require('util')

var tests = []

function FakeStream(_read, _write) {
  stream.Transform.call(this)
  this._read = _read || function() {}
  this._write = _write || function() {}
  StreamEvents.call(this)
}
util.inherits(FakeStream, stream.Transform)

test('is a function', function() {
  assert.equal(typeof StreamEvents, 'function')
})

test('overwrites _read and _write', function() {
  var _readCalled = false
  var _writeCalled = false

  var fs = new FakeStream(function() {
    _readCalled = true
  }, function() {
    _writeCalled = true
  })

  assert.strictEqual(_readCalled, false)
  fs._read()
  assert.strictEqual(_readCalled, true)

  assert.strictEqual(_writeCalled, false)
  fs._write()
  assert.strictEqual(_writeCalled, true)
})

test('emits reading and writing events', function() {
  var eventsCalled = 0

  var fs = new FakeStream()

  fs.on('reading', function() {
    assert.equal(++eventsCalled, 1)
  })
  fs._read()

  fs.on('writing', function() {
    assert.equal(++eventsCalled, 2)
  })
  fs._write()
})

test('works with existing stream', function() {
  var dup = StreamEvents(duplexify())

  var called = false
  dup.on('reading', function() {
    called = true
  })

  dup._read()
  assert(called)
})

function test(message, fn) {
  try {
    fn()
    tests.push({ success: true, fail: false, message: message })
  } catch(e) {
    tests.push({ success: false, fail: true, message: message, error: e })
  }
}

tests.forEach(function(test, index) {
  function black(message) {
    return '\u001b[30m' + message + '\u001b[39m'
  }
  function greenBg(message) {
    return '\u001b[42m' + message + '\u001b[49m'
  }
  function redBg(message) {
    return '\u001b[41m' + message + '\u001b[49m'
  }
  function bold(message) {
    return '\u001b[1m' + message + '\u001b[22m'
  }

  var icon, message
  if (test.success) {
    icon = '✔︎'
    message = greenBg(black(' ' + icon + ' ' + test.message + ' '))
  } else {
    icon = '✖'
    message = redBg(bold(' ' + icon + ' ' + test.message + ' '))
  }

  console.log((index > 0 ? '\n' : '') + message)
  if (test.error) {
    console.log('  ' + test.error.stack)
  }
})