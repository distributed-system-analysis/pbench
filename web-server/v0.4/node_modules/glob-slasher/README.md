# glob-slasher

Prefix an object (key/values) of globs with a slash and normalize. Supports negated globs too. Glob version of slasher module

## Install

```
npm install glob-slasher --save
```

## Usage

Strings

```js
var slasher = require('glob-slasher');

var pathname = '!**/something';
console.log(slasher(pathname)); // OUTPUTS: '!/**/something'
```

Arrays

```js
var slasher = require('glob-slasher');

var globs = ['!**/something', '/here'];
console.log(slasher(globs)); // OUTPUTS: ['!/**/something', '/here']
```

Objects

```js
var slasher = require('glob-slasher');

var globs = {
  '**/some/route': 'index.html'
};
console.log(slasher(globs));

// OUTPUTS:
{
  '/**/some/route': '/index.html'
}
```

## Run Tests

```
npm install
npm test
```
