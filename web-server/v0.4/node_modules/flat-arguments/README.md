# flat-arguments

Flatten a function's argument. Like, really flatten.

## Install

```
npm install flat-arguments --save
```

## Usage

Normal arguments

```js
var flatten = require('flat-arguments');

function letsDoThis () {
  var args = flatten(arguments);
  
  // args = ['arg1', 'arg2']
}

letsDoThis('arg1', 'arg2')
```

Nested arrays as arguments

```js
var flatten = require('flat-arguments');

function letsDoThis () {
  var args = flatten(arguments);
  
  // args = ['arg1', 'arg2', 'arg3']
}

letsDoThis([['arg1', 'arg2'], 'arg3']);
```

Combination of arrays and other types

```js
var flatten = require('flat-arguments');

function letsDoThis () {
  var args = flatten(arguments);
  
  // args = ['arg1', 'arg2', 'arg3']
}

letsDoThis(['arg1', 'arg2'], 'arg3');
```

## Run Tests

```
npm install
npm test
```