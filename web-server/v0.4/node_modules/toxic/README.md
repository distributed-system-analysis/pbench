# toxic

Mutate keys and values in objects. Returns a new version of the object

## Install

```
npm install toxic --save
```

## Usage

```js
var toxic = require('toxic');

var mutatedObject = toxic({
  key1: 'value1',
  key2: 'value2'
}, {
  mutator: function (val) {
    return val + '...'
  }
});

console.log(mutatedObject);
// OUTPUTS:
// {
//   'key1...': 'value1...',
//   'key2...': 'value2...'
// }
```

## API

### toxic(object[, options])

* `object` - The object to perform mutations on.
* `options `
  * `mutator` - Function that gets passed the current key or value. Default returns the value, as is.
  * `keyMutator` - Function used ot mutate the keys. Overrides `mutator`.
  * `valueMutator` - Function used ot mutate the values. Overrides `mutator`.

## Run Tests

```
npm install
npm test
```
