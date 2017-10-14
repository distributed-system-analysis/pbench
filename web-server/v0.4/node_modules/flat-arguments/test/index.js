var flatten = require('../');
var lab = require('lab');
var describe = lab.experiment;
var it = lab.test;
var expect = lab.expect;

describe('flattening', function () {
  
  it('flattens any number of normal values passed into function', function (done) {
    function tester () {
      var args = flatten('arg1', 'arg2');
      expect(args).to.eql(['arg1', 'arg2']);
      done();
    }
    
    tester();
  });
  
  it('flattens a single array', function (done) {
    function tester () {
      var args = flatten(['arg1', 'arg2']);
      expect(args).to.eql(['arg1', 'arg2']);
      done();
    }
    
    tester();
  });
  
  it('flattens arrays of arrays', function (done) {
    function tester () {
      var args = flatten([['arg1', 'arg2'], 'arg3']);
      expect(args).to.eql(['arg1', 'arg2', 'arg3']);
      done();
    }
    
    tester();
  });
  
  it('flattens a combination of arrays and strings', function (done) {
    function tester () {
      var args = flatten(arguments);
      expect(args).to.eql(['arg1', 'arg2', 'arg3']);
      done();
    }
    
    tester(['arg1', 'arg2'], 'arg3');
  });
  
  it('flattens an arguments array to a flat array', function (done) {
    function tester () {
      var args = flatten(arguments);
      expect(args).to.eql(['arg1', 'arg2']);
      done();
    }
    
    tester('arg1', 'arg2');
  });
  
  it('flattens an arguments array of nested arrays', function (done) {
    function tester () {
      var args = flatten(arguments);
      expect(args).to.eql(['arg1', 'arg2', 'arg3']);
      done();
    }
    
    tester([['arg1', 'arg2'], 'arg3']);
  });
  
  it('flattens an arguments array when passed through another function', function (done) {
    function tester () {
      var args = flatten(arguments);
      expect(args).to.eql(['arg1', 'arg2']);
      done();
    }
    
    function passer () {
      tester(arguments);
    }
    
    passer(['arg1', 'arg2']);
  });
  
  it('flattens an arguments array when passed through "N" number of functions', function (done) {
    function tester () {
      var args = flatten(arguments);
      expect(args).to.eql(['arg1', 'arg2']);
      done();
    }
    
    function passer2 () {
      tester(arguments);
    }
    
    function passer1 () {
      passer2(arguments);
    }
    
    
    passer1(['arg1', 'arg2']);
  });
  
});