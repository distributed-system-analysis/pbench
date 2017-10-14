/*jslint node: true, indent: 2, passfail: true */
"use strict";

var util = require('util'),
  Benchmark = require('benchmark'),
  suite = new Benchmark.Suite("Object Definition"),
  Modelo_4_0_2 = require('../versions/4.0.2'),
  Modelo_4_1_0 = require('../versions/4.1.0'),
  Modelo_Current = require('../versions/current'),
  klass = require('klass'),
  augment = require('augment'),
  fiber = require('fiber'),
  print = require('../print');


function TestModeloDefine(impl) {

  return function () {

    var RandomId, Rated, Base, Product, widget;

    RandomId = impl.define(function RandomId() {
      this.id = 4;
    });

    Rated = impl.define(function Rated() {
      this.rating = undefined;
    });
    Rated.prototype.rate = function rate(stars) {
      this.rating = stars;
    };

    Base = impl.define(RandomId, Rated);
    Product = Base.extend(function Product(options) {
      this.name = options.name;
    });
    Product.prototype.rate = function (stars) {
      return Base.prototype.rate.call(this, stars);
    };

    widget = new Product({"name": "widget"});
    return widget.rate(15);

  };

}

function TestModeloInherits(impl) {

  return function () {

    function RandomId() {
      this.id = 4;
    }
    function Rated() {
      this.rating = undefined;
    }
    Rated.prototype.rate = function rate(stars) {
      this.rating = stars;
    };

    function Base() {
      RandomId.call(this);
      Rated.call(this);
    }
    impl.inherits(Base, RandomId, Rated);

    function Product(options) {
      Base.call(this);
      this.name = options.name;
    }
    impl.inherits(Product, Base);
    Product.prototype.rate = function rate(stars) {
      return Base.prototype.rate.call(this, stars);
    };

    var widget = new Product({"name": "widget"});
    return widget.rate(15);

  };

}

function TestUtilInherits() {

  function RandomId() {
    this.id = 4;
  }
  function Rated() {
    RandomId.call(this);
    this.rating = undefined;
  }
  util.inherits(Rated, RandomId);
  Rated.prototype.rate = function rate(stars) {
    this.rating = stars;
  };

  function Base() {
    Rated.call(this);
  }
  util.inherits(Base, Rated);

  function Product(options) {
    Base.call(this);
    this.name = options.name;
  }
  util.inherits(Product, Base);
  Product.prototype.rate = function rate(stars) {
    return Base.prototype.rate.call(this, stars);
  };

  var widget = new Product({"name": "widget"});
  return widget.rate(15);

}

function TestKlass() {

  var RandomId, Rated, Base, Product, widget;

  RandomId = klass(function () {
    this.id = 4;
  });

  // No multiple inheritance so must extend RandomId.
  Rated = RandomId.extend(function () {
    this.rating = undefined;
  }).methods({
    "rate": function (stars) {
      this.rating = stars;
    }
  });

  Base = Rated.extend();
  Product = Base.extend(function (options) {
    this.name = options.name;
  }).methods({
    "rate": function (stars) {
      return this.supr(stars);
    }
  });

  widget = new Product({"name": "widget"});
  return widget.rate(15);

}

function TestAugment() {

  var RandomId, Rated, Base, Product, widget;

  RandomId = augment(Object, function () {
    this.id = 4;
  });

  // No multiple inheritance so must extend RandomId.
  Rated = augment(RandomId, function (uber) {
    this.constructor = function () {
      uber.constructor.call(this);
      this.rating = undefined;
    };
    this.rate = function (stars) {
      this.rating = stars;
    };
  });

  Base = augment(Rated, function (uber) {
    this.constructor = function () {
      uber.constructor.call(this);
    };
  });

  Product = augment(Base, function (uber) {
    this.constructor = function (options) {
      uber.constructor.call(this);
      this.name = options.name;
    };
    this.rate = function (stars) {
      return uber.rate.call(this, stars);
    };
  });

  widget = new Product({"name": "widget"});
  return widget.rate(15);

}

function TestFiber() {

  var RandomId, Rated, Base, Product, widget;

  RandomId = function () {
    return {
      "init": function () {
        this.id = 4;
      }
    };
  };

  Rated = function () {
    return {
      "init": function () {
        this.rating = undefined;
      },
      "rate": function (stars) {
        this.rating = stars;
      }
    };
  };

  Base = fiber.extend(function () {
    return {
      "init": function () {
        return this;
      }
    };
  });
  fiber.mixin(Base, RandomId, Rated);

  Product = Base.extend(function (base) {
    return {
      "init": function (options) {
        this.name = options.name;
      },
      "rate": function (stars) {
        return base.rate.call(stars);
      }
    };
  });

  widget = new Product({"name": "widget"});
  return widget.rate(15);

}

suite.add(
  'Modelo-v4.0.2: define()',
  new TestModeloDefine(Modelo_4_0_2)
);

suite.add(
  'Modelo-v4.1.0: define()',
  new TestModeloDefine(Modelo_4_1_0)
);

suite.add(
  'Modelo-vCurrent: define()',
  new TestModeloDefine(Modelo_Current)
);

suite.add(
  'Modelo-v4.1.0: inherits()',
  new TestModeloInherits(Modelo_4_1_0)
);

suite.add(
  'Modelo-vCurrent: inherits()',
  new TestModeloInherits(Modelo_Current)
);

suite.add(
  'Klass',
  TestKlass
);

suite.add(
  'augment',
  TestAugment
);

suite.add(
  'Fiber',
  TestFiber
);

suite.add(
  'util.inherits',
  TestUtilInherits
);

suite.on('complete', print);

suite.run();
