if (process.version.match(/^v(0\.12\.|[^0])/))
  return

var code = 0
Object.defineProperty(process, 'exitCode', {
  set: function (c) {
    if (typeof c !== 'number')
      throw new TypeError('exitCode must be a number')
    code = c
    if (exiting && code)
      process.exit(code)
  },
  get: function () {
    return code
  },
  enumerable: true, configurable: true
})

var exiting = false
process.on('exit', function (c) {
  exiting = true
  if (code && !c)
    process.exit(code)
})
