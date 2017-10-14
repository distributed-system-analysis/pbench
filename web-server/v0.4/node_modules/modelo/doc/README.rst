=======================
Modelo.js Documentation
=======================

.. contents::

Description
===========

The modelo.js library provides developers with a simplified interface to
multiple, prototypal inheritance. The library exposes a single, primary
function called `define` which generates JavaScript object constructors.

Usage Examples
==============

The modelo.js library can be leveraged in a variety of ways, but the first
call is always to the `define` function.

Object Definitions
------------------

Creating a basic Modelo object is simple::

    var Person = modelo.define();

Now the `Person` variable contains an object constructor that can be used
as though it were any other JavaScript constructor. Prototype attributes can
be added and instances can be created with or without the `new` keyword::

    var Person, myPerson;

    Person = modelo.define();

    Person.prototype.log = function (message) {

        console.log(message);

    }

    myPerson = new Person();
    myPerson.log("I'm just a plain old JavaScript object.")
    // Console Output: "I'm just a plain old JavaScript object."

    myPerson = Person();
    myPerson.log("I'm just a plain old JavaScript object.")
    // Console Output: "I'm just a plain old JavaScript object."

Object Constructors
-------------------

Basic constructors, with no arguments, can be useful in different situation.
Most of the time, however, an object needs custom logic in the constructor.
Creating a Modelo object with custom constructors is the same as creating a
normal, JavaScript object constructor function::

    Var Person, myPerson;

    Person = modelo.define(function () {

        this.name = "Juan Pérez";

    });

    Person.prototype.getName = function () {

        return this.name;

    }

    myPerson = new Person();
    console.log(myPerson.getName());
    // Console Output: "Juan Pérez"

Giving a Modelo object a constructor means simply passing in a constructor
function as a argument to `define`.

The obvious element missing from the above example is that of constructor
arguments. To simplify constructor arguments in a multiple inheritance model
(shown in more detail later), all constructor arguments are now contained
within a single object literal::


    Var Person, myPerson;

    Person = modelo.define(function (options) {

        this.name = options.name || "Juan Pérez";

    });

    Person.prototype.getName = function () {

        return this.name;

    }

    myPerson = new Person();
    console.log(myPerson.getName());
    // Console Output: "Juan Pérez"

    myPerson = new Person({name: "John Smith"});
    console.log(myPerson.getName());
    // Console Output: "John Smith"

Object Inheritance
------------------

Once a Modelo object has been defined it can also be extended. Object extension
in the modelo.js library is a form of prototypal inheritance in which a new
object constructor is created and already has all of the prototype properties
of the object from which it is inherited. This functionality is exposed through
an `extend` method attached to Modelo object constructors. To illustrate::

    var Product, RatedProduct, widget;

    Product = modelo.define(function (options) {

        this.number = options.number || 0;
        this.description = options.description || "";

    });

    Product.prototype.getNumber = function () {

        return this.number;

    };

    Product.prototype.getDescription = function () {

        return this.description;

    };

    RatedProduct = Product.extend(function (options) {

        this.rating = options.rating || 1;

    });

    widget = new RatedProduct({number: 1234,
                                description: "This product is fake.",
                                rating: 5});

    widget.getNumber();  // 1234
    widget.getDescription();  // "This product is fake."
    widget.rating;  // 5

The above example is not intended to be a realistic example of an inheritance
use case but to demonstrate the fact that objects can be inherited.
It is important to notice that inherited constructors are run automatically
without the need for a call to the parent definition. Any functionality of a
parent object constructor can be overwritten in the child constructors as they
are guaranteed to run in inheritance order. Likewise, prototype properties of
the parent object can be safely overridden by the child objects.

Multiple Inheritance
--------------------

Modelo objects allow for the simple inheritance of multiple parent objects. The
same `define` and `extend` methods are used to provide this feature. The above
example for object inheritance could be extended to show multiple inheritance,
but one of the real benefits of multiple inheritance in JavaScript is that it
enables developers to make use of "Mixin" objects. "Mixin", in this scenario,
is when multiple objects contain generalized sets of functionality that can be
shared by multiple other objects. Here is an example::

    var Unique, Timestamped, Person, myPerson;

    Unique = modelo.define(function (options) {

        this.unique = Math.floor(Math.random() * 1000000);

    });

    Timestamped = modelo.define(function (options) {

        this.created = new Date();
        this.modified = new Date();

    });

    Timestamped.prototype.modify = function () {

        this.modified = new Date();

    };

    Person = modelo.define(Unique, Timestamped, function (options) {

        this.name = options.name || "Juan Pérez";

    });


    myPerson = new Person();

    myPerson.unique;  // 123456 (some random number)
    myPerson.created;  // Date object representing creation time
    myPerson.modified;  // Date object representing creation time
    myPerson.name;  // "Juan Pérez"

    myPerson.modify();
    myPerson.modified;  // Date object representing last modified time

Like the earlier example of object inheritance, this example is trivial in its
own right. The important elements to take away from this example are that
multiple object constructors and prototypes can be merged into a single object
constructor and prototype.

Something not immediately apparent from the example is that inheritance flows
from left to right. That is, the last constructor has the ability to overwrite
all previous constructor side-effects.

Detecting Inheritance
---------------------

Arguments of type checking versus behaviour checking aside, it is occasionally
useful to determine if an object is descended from a particular inheritance
chain. To support this, an `isInstance` method is attached to all instances of
Modelo objects. `isInstance` will recursively walk the inheritance chains and
return true or false based on what it finds. As a trivial example::

    var Unique, Timestamped, Product, RatedProduct, myProduct;

    Unique = modelo.define();
    Timestamped = modelo.define();

    Product = modelo.define(Unique, Timestamped);

    RatedProduct = Product.extend();

    myProduct = new RatedProduct();

    myProduct.isInstance(RatedProdcut);  //true

    myProduct.isInstance(Product);  //true

    myProduct.isInstance(Timestamped);  //true

    myProduct.isInstance(Unique);  //true

Alternate Interface
===================

If preferred, this library may be used in a manner identical to the Node.js
standard library util.inherits. All the above information, with respect to how
the library manages inheritance, remains true while using the util.inherits
interface. Simply pass additional bases into the inherits method rather than
a single base.

.. code-block:: javascript

    function Unique() {
        this.unique = Math.floor(Math.random() * 1000000);
    };

    function Timestamped() {
        this.created = new Date();
        this.modified = new Date();
    };
    Timestamped.prototype.modify = function () {
        this.modified = new Date();
    };

    function Person(name) {
        Unique.call(this);
        Timestamped.call(this);
        this.name = name || "Juan Pérez";
    }
    modelo.inherits(Person, Unique, Timestamped);

API Reference
=============

Exports
-------

The modelo.js library exports a function that generates Modelo objects. A proxy
for this function has been created as the root export for ease of use::

    var modelo = require('modelo');

    typeof modelo === "function"; // true

    typeof modelo.define === "function"; // true

    typeof modelo.inherits === "function"; // true

In a browser, the modelo.js library is loaded in the global `modelo` object::

    typeof modelo === "function"; // true

    typeof modelo.define === "function"; // true

    typeof modelo.inherits === "function"; // true

inherits(child, parent, parent, ...)
------------------------------------

This function accepts a child function and any number of parent function. It
does not return anything. Instead it modifies the child prototype in a way
nearly identical to the Node.js util.inherits. The behaviour of leaching
prototype attributes from multiple parent functions is identical to that of
the 'define()' function below.

define()
--------

The `define` function takes any number of constructor functions and produces
a new Modelo object. Modelo objects contain a composite of all prototype
attributes attached to the given constructors. Prototype elements are leached
in order of the first constructor passed to `define` to the last. This is also
the order of precedence for constructor execution in the new Modelo object. The
last constructor and prototype will overwrite any earlier constructor and
prototype in the event of a conflict.

::

    var MyObject = modelo.define();

Modelo Object
-------------

Modelo objects are generated with either a call to `define` or to `extend`.
They can be initialized with, or without, the `new` keyword.

::

    var myInstance = new MyObject();
    // or
    var myInstance = MyObject();

extend()
^^^^^^^^

All Modelo objects can be extended through the `extend` method. This method
operates exactly as the root `define` function with the exception that the
current Modelo object is always passed in as the first argument. A call to::

    MyObject.extend();

is equivalent to::

    modelo.define(MyObject);

isInstance(parent)
^^^^^^^^^^^^^^^^^^

Instances of Modelo objects can call `isInstance` to determine if they are
inherited from a given parent constructor::

    myInstance.instanceOf(MyObject);
