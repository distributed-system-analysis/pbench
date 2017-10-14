var stream = require('stream')
var streamEvents = require('./')
var util = require('util')

function MyStream() {
  stream.Duplex.call(this)
  streamEvents.call(this)
}
util.inherits(MyStream, stream.Duplex)

MyStream.prototype._read = function(chunk) {
  console.log('_read called as usual')
  this.push(new Buffer(chunk))
  this.push(null)
}

MyStream.prototype._write = function() {
  console.log('_write called as usual')
}

var stream = new MyStream

stream.on('reading', function() {
  console.log('stream is being asked for data')
})

stream.on('writing', function() {
  console.log('stream is being sent data')
})

stream.pipe(stream)
