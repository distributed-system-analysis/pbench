module.exports = function (data, convertObject) {

  if (!data) {
    data = [];
  }

  if (isArgs(data)) {
    data = [].splice.call(data, 0);
  }

  if (isObject(data) && convertObject) {
    data = values(data);
  }

  return Array.isArray(data)
    ? data
    : [data];
};

function isObject (obj) {

  return Object.prototype.toString.call(obj) === "[object Object]"
}

function isArgs( item ) {

    return Object.prototype.toString.call( item ) === '[object Arguments]';
}

function values (obj) {

  return Object.keys(obj).map(function (key) {

    return obj[key];
  });
}
