|![retry-request](logo.png)
|:-:
|Retry a [request][request] with built-in [exponential backoff](https://developers.google.com/analytics/devguides/reporting/core/v3/coreErrors#backoff).

```sh
$ npm install --save retry-request
```
```js
var request = require('retry-request');
```

It should work the same as `request` in both callback mode and stream mode.

Note: This module only works when used as a readable stream, i.e. POST requests aren't supported  ([#3](https://github.com/stephenplusplus/retry-request/issues/3)).

#### Callback

`urlThatReturns503` will be requested 3 total times before giving up and executing the callback.

```js
request(urlThatReturns503, function (err, resp, body) {});
```

#### Stream

`urlThatReturns503` will be requested 3 total times before giving up and emitting the `response` and `complete` event as usual.

```js
request(urlThatReturns503)
  .on('error', function () {})
  .on('response', function () {})
  .on('complete', function () {});
```

## request(requestOptions, [opts], [cb])

### requestOptions

Passed directly to `request`. See the list of options supported: https://github.com/request/request/#requestoptions-callback.

### opts *(optional)*

#### `opts.objectMode`

Type: `Boolean`

Default: `false`

Set to `true` if your custom `opts.request` function returns a stream in object mode.

#### `opts.retries`

Type: `Number`

Default: `2`

```js
var opts = {
  retries: 4
};

request(urlThatReturns503, opts, function (err, resp, body) {
  // urlThatReturns503 was requested a total of 5 times
  // before giving up and executing this callback.
});
```

#### `opts.shouldRetryFn`

Type: `Function`

Default: Returns `true` if [http.incomingMessage](https://nodejs.org/api/http.html#http_http_incomingmessage).statusCode is < 200 or >= 400.

```js
var opts = {
  shouldRetryFn: function (incomingHttpMessage) {
    return incomingHttpMessage.statusMessage !== 'OK';
  }
};

request(urlThatReturnsNonOKStatusMessage, opts, function (err, resp, body) {
  // urlThatReturnsNonOKStatusMessage was requested a
  // total of 3 times, each time using `opts.shouldRetryFn`
  // to decide if it should continue before giving up and
  // executing this callback.
});
```

#### `opts.request`

Type: `Function`

Default: [`request`][request]

*NOTE: If you override the request function, and it returns a stream in object mode, be sure to set `opts.objectMode` to `true`.*

```js
var originalRequest = require('request').defaults({
  pool: {
    maxSockets: Infinity
  }
});

var opts = {
  request: originalRequest
};

request(urlThatReturns503, opts, function (err, resp, body) {
  // Your provided `originalRequest` instance was used.
});
```

### cb *(optional)*

Passed directly to `request`. See the callback section: https://github.com/request/request/#requestoptions-callback.

[request]: https://github.com/request/request
