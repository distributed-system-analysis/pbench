'use strict';

module.exports = function (template, args) {
  if (!args) {
    return interpolate.bind(null, template);
  }

  return interpolate(template, args);
};

function interpolate(template, args) {
  return template.replace(/{([^}]*)}/g, function (match, key) {
    return key in args ? args[key] : match;
  });
}