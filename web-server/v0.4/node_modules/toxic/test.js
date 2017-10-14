var toxic = require('./index');
var test = require('tape');

test('throws an error for non-object', function (t) {
  
  var threw = false;
  
  try {
    toxic('test');
  }
  catch (e) {
    threw = true;
  }
  
  t.ok(threw, 'threw error on non-object');
  t.end();
});

test('does nothing if no mutator provided', function (t) {
  
  var obj = {
    key1: 'value1',
    key2: 'value2'
  };
  
  var mutatedObj = toxic(obj);
  
  t.deepEqual(mutatedObj, {
    key1: 'value1',
    key2: 'value2'
  }, 'not mutated');
  
  t.end();
});

test('mutates all keys and values', function (t) {
  
  var obj = {
    key1: 'value1',
    key2: 'value2'
  };
  
  var mutatedObj = toxic(obj, {
    mutator: function (val) {
      return val + 'a';
    }
  });
  
  t.deepEqual(mutatedObj, {
    key1a: 'value1a',
    key2a: 'value2a'
  }, 'mutated all values');
  
  t.end();
});

test('mutates only the keys', function (t) {
  
  var obj = {
    key1: 'value1',
    key2: 'value2'
  };
  
  var mutatedObj = toxic(obj, {
    keyMutator: function (val) {
      return val + 'a';
    }
  });
  
  t.deepEqual(mutatedObj, {
    key1a: 'value1',
    key2a: 'value2'
  }, 'mutated');
  
  t.end();
});

test('mutates only the values', function (t) {
  
  var obj = {
    key1: 'value1',
    key2: 'value2'
  };
  
  var mutatedObj = toxic(obj, {
    valueMutator: function (val) {
      return val + 'a';
    }
  });
  
  t.deepEqual(mutatedObj, {
    key1: 'value1a',
    key2: 'value2a'
  }, 'mutated');
  
  t.end();
});

test('key or value specific mutator overrides mutator', function (t) {
  
  var obj = {
    key1: 'value1',
    key2: 'value2'
  };
  
  var mutatedObj = toxic(obj, {
    mutator: function (val) {
      return val +'a';
    },
    keyMutator: function (val) {
      return val + 'b';
    }
  });
  
  t.deepEqual(mutatedObj, {
    key1b: 'value1a',
    key2b: 'value2a'
  }, 'mutated keys');
  
  var mutatedObj = toxic(obj, {
    mutator: function (val) {
      return val +'a';
    },
    valueMutator: function (val) {
      return val + 'b';
    }
  });
  
  t.deepEqual(mutatedObj, {
    key1a: 'value1b',
    key2a: 'value2b'
  }, 'mutated values');
  
  t.end();
});