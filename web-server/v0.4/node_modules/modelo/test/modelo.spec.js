/*jslint node: true, indent: 2, passfail: true, newcap: true */
/*globals describe, it */

"use strict";

var expect = require('expect.js'),
  modelo = require('../modelo/modelo.js');

describe('The Modelo library', function () {

  it('supports the basic style of object definition', function () {

    var T = modelo.define(),
      i = new T();

    expect(T).to.be.ok();

    expect(T).to.be.a('function');

    expect(T.extend).to.be.a('function');

    expect(i).to.be.a(T);

  });

  it('optionally supports the new keyword', function () {

    var T = new modelo(),
      i = new T();

    expect(T).to.be.ok();

    expect(T).to.be.a('function');

    expect(T.extend).to.be.a('function');

    expect(i).to.be.a(T);

  });

  it('supports the constructor style of object definition', function () {

    var T = modelo.define(function (options) {
        this.name = options.name || 'Juan Pérez';
      }),
      i = new T();

    expect(i).to.be.ok();

    expect(i.name).to.be('Juan Pérez');

    i = new T({name: 'Juan Pueblo'});

    expect(i.name).to.be('Juan Pueblo');

  });

  it('supports the mix-in style of object definition', function () {

    var Person,
      Talker,
      Walker,
      Customer,
      test_customer;

    Person = modelo.define(function (options) {
      this.name = options.name || 'Juan Pérez';
    });

    Person.prototype.hello = function () {
      return "Hello " + this.name + "!";
    };

    Talker = modelo.define(function (options) {
      this.language = options.language || 'ES';
    });

    Talker.prototype.speak = function () {
      if (this.language === 'EN') {
        return "Hello.";
      }

      if (this.language === 'ES') {
        return "Hola.";
      }

      return "...";
    };

    Walker = modelo.define(function (options) {
      this.legs = options.legs || 2;
    });

    Walker.prototype.walk = function () {
      return "These " + this.legs + " boots were made for walkin'.";
    };

    Customer = modelo.define(Person, Talker, Walker);

    expect(Customer.prototype.hello).to.be.a('function');
    expect(Customer.prototype.speak).to.be.a('function');
    expect(Customer.prototype.walk).to.be.a('function');

    test_customer = new Customer();

    expect(test_customer).to.be.a(Customer);

    expect(test_customer.hello()).to.be('Hello Juan Pérez!');
    expect(test_customer.speak()).to.be('Hola.');
    expect(test_customer.walk()).to.be("These 2 boots were made for walkin'.");

  });

  it('can recognize inhertied objects', function () {

    var Person,
      Talker,
      Walker,
      Customer,
      Empty_Mixin,
      Extended_Customer,
      test_customer,
      extended_test_customer;

    Person = modelo.define(function (options) {
      this.name = options.name || 'Juan Pérez';
    });

    Person.prototype.hello = function () {
      return "Hello " + this.name + "!";
    };

    Talker = modelo.define(function (options) {
      this.language = options.language || 'ES';
    });

    Talker.prototype.speak = function () {
      if (this.language === 'EN') {
        return "Hello.";
      }

      if (this.language === 'ES') {
        return "Hola.";
      }

      return "...";
    };

    Walker = modelo.define(function (options) {
      this.legs = options.legs || 2;
    });

    Walker.prototype.walk = function () {
      return "These " + this.legs + " boots were made for walkin'.";
    };

    Customer = modelo.define(Person, Talker, Walker);

    Empty_Mixin = modelo.define();

    Extended_Customer = Customer.extend(Empty_Mixin);

    test_customer = new Customer();
    extended_test_customer = new Extended_Customer();

    expect(test_customer.isInstance(Customer)).to.be(true);
    expect(test_customer.isInstance(Person)).to.be(true);
    expect(test_customer.isInstance(Talker)).to.be(true);
    expect(test_customer.isInstance(Walker)).to.be(true);
    expect(test_customer.isInstance(function () {
      return null;
    })).to.be(false);

    expect(extended_test_customer.isInstance(Customer)).to.be(true);
    expect(extended_test_customer.isInstance(Empty_Mixin)).to.be(true);
    expect(extended_test_customer.isInstance(Person)).to.be(true);
    expect(extended_test_customer.isInstance(Walker)).to.be(true);
    expect(extended_test_customer.isInstance(Talker)).to.be(true);
    expect(extended_test_customer.isInstance(function () {
      return null;
    })).to.be(false);

  });

  it("mimics the built-in utils", function () {

    function Base() {
      this.created = true;
    }
    Base.prototype.test = function test() {
      this.tested = true;
    };

    function Extension() {
      Base.call(this);
    }
    modelo.inherits(Extension, Base);

    var e = new Extension();

    expect(e.created).to.be(true);
    expect(e.test).to.be.ok();
    e.test();
    expect(e.tested).to.be(true);
    expect(e instanceof Base).to.be(true);
    expect(Extension.super_).to.be(Base);

  });

  it("expands on the built-in utils", function () {

    function Base() {
      this.created = true;
    }
    Base.prototype.test = function test() {
      this.tested = true;
    };
    function Base2() {
      this.multiple = true;
    }

    function Extension() {
      Base.call(this);
      Base2.call(this);
    }
    modelo.inherits(Extension, Base, Base2);

    var e = new Extension();

    expect(e.created).to.be(true);
    expect(e.test).to.be.ok();
    e.test();
    expect(e.tested).to.be(true);
    expect(e.isInstance(Base)).to.be(true);
    expect(e.isInstance(Base2)).to.be(true);
    expect(e.isInstance(Extension)).to.be(true);

  });

});
