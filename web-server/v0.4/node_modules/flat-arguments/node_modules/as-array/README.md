# as-array

Make any value an array

## Install

```
npm install as-array --save
```

## Usage

```js
var asArray = require('as-array');

asArray() === [];
asArray('my string') === ['my string'];
asArray([1,2,3]) === [1,2,3];

function tester () {
  asArray(arguments) === ['arg1', 'arg2'];
}
tester('arg1', 'arg2');
```

### asArray(data[, convertObject])

* `data` - any data type to convert to an array
* `convertObject` - OPTIONAL - `boolean` - pull values from object as array content

## Run Tests

```
npm install
npm test
```