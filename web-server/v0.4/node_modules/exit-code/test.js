if (!isNaN(process.argv[2])) {
  require('./')
  process.exitCode = +process.argv[2]
  setTimeout(function() {
    process.exit()
  })
  return
}

if (!isNaN(process.argv[3])) {
  require('./')
  setTimeout(function () {
    process.on('exit', function () {
      process.exitCode = +process.argv[3]
    })
  })
  return
}

var test = require('tap').test
var spawn = require('child_process').spawn
var node = process.execPath
var codes = [0, 1, 2, 3, 4, 5]

test('immediate exit', function (t) {
  t.plan(codes.length)
  codes.forEach(function (want) {
    spawn(node, [__filename, want]).on('close', function (found) {
      t.equal(found, want, 'immediate exit ' + want)
    })
  })
})

test('deferred exit', function (t) {
  t.plan(codes.length)
  codes.forEach(function (want) {
    spawn(node, [__filename, 'x', want]).on('close', function (found) {
      t.equal(found, want, 'deferred exit ' + want)
    })
  })
})
