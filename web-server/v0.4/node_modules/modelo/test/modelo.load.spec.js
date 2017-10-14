/*jslint node: true, indent: 2, passfail: true, newcap: true */
/*globals describe, it */

"use strict";

var expect = require('expect.js'),
  modelo = require('../modelo/modelo.js');

describe('The Modelo module loader', function () {

  it('works in the current environment.', function () {

    expect(modelo).to.be.ok();

  });

});
