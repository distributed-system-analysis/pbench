# gcp-metadata
> Get the metadata from a Google Cloud Platform environment

```sh
$ npm install --save gcp-metadata
```
```js
var gcpMetadata = require('gcp-metadata')
```

#### Access all metadata
```js
gcpMetadata.instance(function(err, response, metadata) {
  // All metadata properties
})
```

#### Access specific properties
```js
gcpMetadata.instance('hostname', function(err, response, metadata) {
  // All metadata properties
})
```

#### Access specific properties with query parameters
```js
gcpMetadata.instance({
  property: 'tags',
  qs: { alt: 'text' }
}, function(err, response, metadata) {
  // Tags as newline-delimited list
})
```
