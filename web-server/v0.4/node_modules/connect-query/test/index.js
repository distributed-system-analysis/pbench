var query = require('../');
var expect = require('chai').expect;
var request = require('supertest');
var connect = require('connect');

describe('query', function () {
  
  it('parses the query paremeters from a url', function (done) {
    var app = connect()
      .use(query())
      .use(function (req, res, next) {
        res.end(JSON.stringify(req.query));
      });
    
    request(app)
      .get('/?name=test&email=no')
      .expect(function (data) {
        expect(JSON.parse(data.text)).to.eql({
          name: 'test',
          email: 'no'
        });
      })
      .end(done);
  });
  
  it('should default to empty object', function (done) {
    var app = connect()
      .use(query())
      .use(function (req, res, next) {
        res.end(JSON.stringify(req.query));
      });
    
    request(app)
      .get('/')
      .expect(function (data) {
        expect(JSON.parse(data.text)).to.eql({});
      })
      .end(done);
  });
  
});