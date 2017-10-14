/*
The MIT License (MIT)
Copyright (c) 2012 Kevin Conway

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

/*jslint node: true, indent: 2, passfail: true */
/*global define */
"use strict";

function arrayFromArguments() {
  var length = arguments.length,
    args = [],
    x;

  for (x = 0; x < length; x = x + 1) {
    args[x] = arguments[x];
  }

  return args;
}

function copyPrototype(take, give) {
  var keys = Object.keys(give.prototype),
    length = keys.length,
    x;

  for (x = 0; x < length; x = x + 1) {
    take.prototype[keys[x]] = give.prototype[keys[x]];
  }
}

function ModeloBase() {
  return this;
}

function isInstance(self, bases, base) {

  var length = bases.length,
    x;

  if (base === self) {
    return true;
  }

  for (x = 0; x < length; x = x + 1) {
    if (base === bases[x]) {
      return true;
    }

    if (!!bases[x].prototype.isInstance &&
          bases[x].prototype.isInstance(base)) {
      return true;
    }
  }

  return false;

}

function extend() {
  return define.apply(undefined, arguments);
}

function define() {

  var constructors = arrayFromArguments.apply(undefined, arguments),
    length = constructors.length,
    x;

  function ModeloWrapper() {

    var y;

    for (y = 0; y < length; y = y + 1) {
      if (arguments.length > 0) {
        constructors[y].apply(this, arguments);
      } else {
        constructors[y].call(this, {});
      }
    }

  }

  for (x = 0; x < length; x = x + 1) {
    copyPrototype(ModeloWrapper, constructors[x]);
  }
  if (length > 0) {
    ModeloWrapper.constructor = constructors[length - 1].constructor;
  }

  ModeloWrapper.prototype.isInstance = isInstance.bind(
    undefined,
    ModeloWrapper,
    constructors
  );
  ModeloWrapper.extend = extend.bind(undefined, ModeloWrapper);

  return ModeloWrapper;

}

function inherits() {

  var constructors = arrayFromArguments.apply(undefined, arguments),
    to = constructors.shift(),
    length = constructors.length,
    x;

  if (length > 0) {
    // This method brought to you by Node.js util module.
    // https://github.com/joyent/node/blob/master/lib/util.js
    to.prototype = Object.create(
      constructors[length - 1].prototype,
      {
        constructor: {
          value: to,
          enumerable: false,
          writable: true,
          configurable: true
        }
      }
    );
  }

  for (x = 0; x < length; x = x + 1) {
    copyPrototype(to, constructors[x]);
  }

  to.prototype.isInstance = isInstance.bind(
    undefined,
    to,
    constructors
  );
  to.extend = extend.bind(undefined, to);

  return to;

}

define.define = define;
define.inherits = inherits;

module.exports = define;
