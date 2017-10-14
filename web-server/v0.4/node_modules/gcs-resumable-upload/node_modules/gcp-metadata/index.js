'use strict'

var extend = require('extend')
var request = require('retry-request')

var BASE_URL = 'http://metadata.google.internal/computeMetadata/v1'

var gcpMetadata = {
  _buildMetadataAccessor: function (type) {
    return function (options, callback) {
      if (typeof options === 'function') {
        callback = options
        options = {}
      }

      if (typeof options === 'string') {
        options = {
          property: options
        }
      }

      var property = options.property ? '/' + options.property : ''

      var reqOpts = extend(true, {
        uri: BASE_URL + '/' + type + property,
        headers: { 'Metadata-Flavor': 'Google' }
      }, options)
      delete reqOpts.property

      return request(reqOpts, callback)
    }
  }
}

gcpMetadata.instance = gcpMetadata._buildMetadataAccessor('instance')
gcpMetadata.project = gcpMetadata._buildMetadataAccessor('project')

module.exports = gcpMetadata

