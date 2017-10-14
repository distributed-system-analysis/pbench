/*jslint node: true, indent: 2, passfail: true, newcap: true */
/*globals describe, it */

"use strict";

var expect = require('expect.js'),
  modelo = require('../modelo/modelo.js');

describe('The Modelo interface', function () {

  it('matches the documentation', function () {

    expect(typeof modelo).to.be("function");

    expect(typeof modelo.define).to.be("function");

  });

});
