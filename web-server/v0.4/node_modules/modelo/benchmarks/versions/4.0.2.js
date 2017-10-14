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
"use strict";

var define;

define = function () {

  var constructors = Array.prototype.slice.call(arguments),
    Modelo,
    x,
    p;

  /*
    Here the new constructor is built. As each new instance is
    built the Modelo constructor will iterate over the constructors
    given to 'define' and call them in the current context. This
    allows for a Modelo to accept multiple constructors and process
    them in a deterministic way.

    Constructors can be any function, including other Modelo
    constructors. There are no restrictions placed on what the
    given functions can do. Each function is bound to the current
    context so all references to 'this' are directed at the new
    instance being created.
  */
  Modelo = function () {

    var y,
      cArgs = Array.prototype.slice.call(arguments);

    cArgs[0] = cArgs[0] !== undefined ? cArgs[0] : {};

    for (y = 0; y < constructors.length; y = y + 1) {

      constructors[y].apply(this, cArgs);

    }

  };

  /*
    Here the 'prototype' attribute of each given constructor is
    processed. Every attribute directly attached to the 'prototype'
    of a constructor is grafted on to the prototype of the new
    Modelo constructor.
  */
  for (x = 0; x < constructors.length; x = x + 1) {

    for (p in constructors[x].prototype) {

      if (constructors[x].prototype.hasOwnProperty(p)) {

        Modelo.prototype[p] = constructors[x].prototype[p];

      }

    }

  }

  /*
    The 'extend' is attached directly to the constructor to make it
    similar to a class method. It simply wraps a new call to
    'define' and adds the current 'Modelo' constructor as the first
    argument.

    This provides a slightly easier way to inherity from a given
    Modelo. The same behaviour, however, can be achieved by calling
    'define' with the target Modelo as the first argument. The
    following snippets, for example, are equivalent:

        var MyThing = Modelo.define(),
            MySubThing = MyThing.extend();

        var MyThing = Modelo.define(),
            MySubThing = Modelo.define(MyThing);

  */
  Modelo.extend = function () {

    var extensions = Array.prototype.slice.call(arguments);

    extensions.splice(0, 0, Modelo);

    return define.apply({}, extensions);

  };

  /*
    This utility method determines whether or not a given instance
    is derived from a given constructor.

    To provide this facility, the method will first compare the
    identity of the provided constructor against that of the
    Modelo that produced the instance. For example:

        var MyThing = Modelo.define(),
            myInstance = new MyThing();

        myInstance.isInstance(MyThing); // true

    Next it will compare the given constructor to all the
    constructors given at the time of the Modelo definition and
    recursively call 'isInstance' on those constructors if
    applicable:

        var MyConstructor = function () {},
            MyThing = Modelo.define(MyConstructor),
            myInstance = new MyThing();

        myInstance.isInstance(MyConstructor); // true

    It would be difficult to create an inheritance chain so deep
    and complex that this method would cause any significant
    disruption of runtime. However, it's worth noting that it is
    a recursive function and will always run an exhaustive search.
  */
  Modelo.prototype.isInstance = function (f) {

    var z;

    if (f === Modelo) {

      return true;

    }

    for (z = 0; z < constructors.length; z = z + 1) {

      if (f === constructors[z]) {

        return true;

      }

      if (!!constructors[z].prototype.isInstance &&
            constructors[z].prototype.isInstance(f)) {

        return true;

      }

    }

    return false;

  };

  return Modelo;

};

/*
  This circular reference helps provide a more flexible interface
  and allows for all of the following calls to function identically:

      var MyThing = Modelo();

      var MyThing = new Modelo();

      var MyThing = Modelo.define();

      var MyThing = new Modelo.define();
*/
define.define = define;

module.exports = define;
