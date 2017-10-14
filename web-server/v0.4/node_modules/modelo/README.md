# Modelo.js [![Current Build Status](https://travis-ci.org/kevinconway/Modelo.js.png?branch=master)](https://travis-ci.org/kevinconway/Modelo.js)

**A multiple inheritance utility for JavaScript.**

## Why?

Inheritance libraries today all seem to enforce the same clunky interface
style. The only one of any merit these days is 'util.inherits' from the Node.js
standard library. Only problem: no multiple inheritance.

Wouldn't it be great if 'util.inherits' supported multiple inheritance *and*
it stayed fast too?

That's this library. That's why it exists.

## util.inherits

The 'modelo.inherits' function can act as a drop in replacement for
'util.inherits'. Already have a code base that you want to start extending? No
problem.

```javascript

    var modelo = require('modelo');

    function Base() {
        // Base object constructor
    }
    Base.prototype.baseMethod = function baseMethod() {
        console.log('Method from base object.');
    }

    function Extension() {
        // Sub-object constructor
    }
    // util.inherits(Extension, Base);
    modelo.inherits(Example, Base);

    new Extension() instanceof Base; // true

```

## Multiple Inheritance

Once you need to extend multiple base objects, just put more base objects in
the call to 'inherits'.

```javascript

    var modelo = require('modelo');

    function MixinOne() {}
    function MixinTwo() {}

    function Combined() {}
    modelo.inherits(Combined, MixinOne, MixinTwo);

    var instance = new Combined();

    instance.isInstance(Combined); // true
    instance.isInstance(MixinOne); // true
    instance.isInstance(MixinTwo); // true

```

Unfortunately, there is no way to make 'instanceof' work with multiple
inheritance. To replace it, simply use the 'isInstance' method that gets added
to your instances. It will return true for any base object in the inheritance
tree.

Additionally, the 'super_' attribute is still present on the new constructor in
multiple inheritance but it only references the first prototype present in the
call to 'inherits'. It is provided only for compatibility with `util.inherits`
and, when using multiple inheritance, the 'super_' attribute should be avoided
in favour of calling the target prototype directly if the form of
`<Constructor>.prototype.<method>.call(this, ...)` or
`<Constructor>.prototype.<method>.apply(this, ...)`.

## You Said Something About Fast?

All inheritance libraries have their cost. When the overhead in question affects
the speed of object definition and creation, though, that cost must be kept
to a minimum. Here is how this library compares to the competition:

### Object Definition

The typical benchmark you will see while researching inheritance tools is one
that measures the cost of an object prototype, or class, definition followed by
the creation of a single instance. The following results are based on a test
which does just that. Each library produces an equivalent inheritance tree and
spawns an instance. The full source of the benchmark can be found in
'benchmarks/comparisons/define.js'.

The approximate results:

| Name          | % Slower   |
----------------|-------------
| Fiber         | 0.0000 %   |
| util.inherits | 24.010 %   |
| augment       | 64.601 %   |
| Modelo        | 65.594 %   |
| Klass         | 74.658 %   |


The [Fiber][] library is the clear winner with a 24% difference in run-time cost
from the Node.js 'util.inherits'. Considering the implementation of
'util.inherits' is effectively a two line wrapper around the 'Object.create'
built-in, it's quite a surprise that Fiber is *that* much faster. Now, the
*actual* difference between Fiber and 'util.inherits' is something on the order
of ~0.00008 seconds which, frankly, is inconsequential.

In fact, even the difference between Fiber and the bottom three libraries
is inconsequential, not because the difference is not statistically
significant but, because this benchmark only represents the time required to
define a "class", or object prototype. This is something that happens, at most,
once for each class, or object prototype, defined in a code base. These
run-time costs simply do not matter unless your code base generates hundreds
of thousands of "class" definitions.

### Instance Creation

A far more realistic measurement of overhead is the time it takes to create an
instance of an object defined using an inheritance library. After all, creating
instances necessarily happens far more often than defining the prototype:

| Name          | % Slower   |
----------------|-------------
| Modelo        | 0.0000 %   |
| util.inherits | 3.4355 %   |
| Fiber         | 45.017 %   |
| augment       | 48.284 %   |
| Klass         | 161.79 %   |

The above results are deceptive. While it appears as though Modelo is faster
than the others, including the Node.js 'util.inherits', the reality is that
the run-time difference between these libraries is so small that it exceeds
the microsecond resolution of the timer used in the benchmarks. For all intents
and purposes there is no measurable difference between any of these libraries.

### Conclusion

When it comes down to it, you should pick your inheritance tool chain based on
its interface. The run-time cost of most inheritance libraries on the market
today is sub-microsecond and unlikely to affect the performance of your
code.

Note: If you find a flaw in any of the benchmarks used please open an issue on
GitHub.

## Setup

### Node.js

This package is published through NPM under the name 'modelo':

    $ npm install modelo

Once installed, simply 'require("modelo")'.

### Browser

This module uses browserify to create a browser compatible module. The default
grunt workflow for this project will generate both a full and minified browser
script in a build directory which can be included as a ```<script>``` tag:

    <script src="modelo.browser.min.js"></script>

The package is exposed via the global name 'modelo'.

### Tests

Running the ```npm test``` command will kick off the default grunt workflow. This
will lint using jslint, run the mocha/expect tests, generate a browser module,
and generate browser tests.

### Benchmarks

Running ```grunt benchmark``` will run the benchmarks discussed above. You can
optionally install the micro-time library (```npm install microtime```) to get
microsecond precision.

## License

This project is released and distributed under an MIT License.

    Copyright (C) 2012 Kevin Conway

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to
    deal in the Software without restriction, including without limitation the
    rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
    sell copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
    IN THE SOFTWARE.

## Contributors

### Style Guide

All code must validate against JSlint.

### Testing

Mocha plus expect. All tests and functionality must run in Node.js and the
browser.

### Contributor's Agreement

All contribution to this project are protected by the contributors agreement
detailed in the CONTRIBUTING file. All contributors should read the file before
contributing, but as a summary::

    You give us the rights to distribute your code and we promise to maintain
    an open source release of anything you contribute.


[Fiber]: <https://github.com/linkedin/Fiber>
