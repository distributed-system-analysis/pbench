# methmeth
> Call a method on an object in an Array.prototype callback.


```sh
$ npm install --save methmeth
```
```js
var meth = require('methmeth');

var friends = [
  {
    name: 'passy',
    hobby: 'carrots',
    getInfo: function () {
      return this.name + ' likes ' + this.hobby;
    }
  },
  {
    name: 'sindre',
    vehicle: 'unicorn taxi',
    getInfo: function () {
      return this.name + ' drives a ' + this.vehicle;
    }
  },
  {
    name: 'addy',
    invented: 'google *',
    getInfo: function () {
      return this.name + ' created ' + this.invented;
    }
  }
];
```

#### Before
```js
var myFriends = friends.map(function (item) {
  return item.getInfo();
}).join('\n');
// passy likes carrots
// sindre drives a unicorn taxi
// addy created google *
```

#### After
```js
friends.map(meth('getInfo')).join('\n');
// passy likes carrots
// sindre drives a unicorn taxi
// addy created google *
```

#### Pre-fill arguments
```js
var friends = [
  {
    name: 'dave',
    passion: 'dried mango',
    getInfo: function (emotion) {
      return this.name + ' loves ' + this.passion + emotion;
    }
  }
];

friends.map(meth('getInfo', '!!!!')).join('\n');
// dave loves dried mango!!!!
```

#### Related

- [propprop](https://github.com/stephenplusplus/propprop) - Pluck a property out of an object in an Array.prototype callback.
