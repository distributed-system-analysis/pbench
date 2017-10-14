'use strict';

var assign = require('object-assign');
var async = require('async');
var fs = require('fs');
var GoogleAuth = require('google-auth-library');
var gcpMetadata = require('gcp-metadata');
var path = require('path');
var request = require('request');

function Auth(config) {
  if (!(this instanceof Auth)) {
    return new Auth(config);
  }

  this.authClientPromise = null;
  this.authClient = null;
  this.config = config || {};
  this.environment = {};
}

Auth.prototype.authorizeRequest = function (reqOpts, callback) {
  this.getToken(function (err, token) {
    if (err) {
      callback(err);
      return;
    }

    var authorizedReqOpts = assign({}, reqOpts);
    authorizedReqOpts.headers = authorizedReqOpts.headers || {};
    authorizedReqOpts.headers.Authorization = 'Bearer ' + token;

    callback(null, authorizedReqOpts);
  });
};

Auth.prototype.getAuthClient = function (callback) {
  var self = this;
  var config = self.config;

  if (!this.authClientPromise) {
    if (this.authClient) {
      this.authClientPromise = Promise.resolve(this.authClient);
    } else {
      this.authClientPromise = new Promise(createAuthClientPromise);
    }
  }

  this.authClientPromise.then(callback.bind(null, null)).catch(callback);

  function createAuthClientPromise(resolve, reject) {
    var googleAuth = new GoogleAuth();
    var keyFile = config.keyFilename || config.keyFile;

    if (config.credentials) {
      googleAuth.fromJSON(config.credentials, addScope);
    } else if (keyFile) {
      keyFile = path.resolve(process.cwd(), keyFile);

      fs.readFile(keyFile, function (err, contents) {
        if (err) {
          reject(err);
          return;
        }

        try {
          googleAuth.fromJSON(JSON.parse(contents), addScope);
        } catch(e) {
          var authClient = new googleAuth.JWT();
          authClient.keyFile = keyFile;
          authClient.email = config.email;
          addScope(null, authClient);
        }
      });
    } else {
      googleAuth.getApplicationDefault(addScope);
    }

    function addScope(err, authClient, projectId) {
      if (err) {
        reject(err);
        return;
      }

      if (authClient.createScopedRequired && authClient.createScopedRequired()) {
        if (!config.scopes || config.scopes.length === 0) {
          var scopeError = new Error('Scopes are required for this request.');
          scopeError.code = 'MISSING_SCOPE';
          reject(scopeError);
          return;
        }
      }

      authClient.scopes = config.scopes;
      self.authClient = authClient;
      self.projectId = projectId || authClient.projectId;

      resolve(authClient);
    }
  }
};

Auth.prototype.getCredentials = function (callback) {
  var self = this;

  this.getAuthClient(function (err, client) {
    if (err) {
      callback(err);
      return;
    }

    if (client.email && client.key) {
      callback(null, {
        client_email: client.email,
        private_key: client.key
      });
      return;
    }

    if (!client.authorize) {
      callback(new Error('Could not get credentials without a JSON, pem, or p12 keyfile.'));
      return;
    }

    client.authorize(function (err) {
      if (err) {
        callback(err);
        return;
      }

      self.getCredentials(callback);
    });
  });
};

Auth.prototype.getEnvironment = function (callback) {
  var self = this;

  async.parallel([
    this.isAppEngine.bind(this),
    this.isCloudFunction.bind(this),
    this.isComputeEngine.bind(this),
    this.isContainerEngine.bind(this)
  ], function () {
    callback(null, self.environment);
  });
};

Auth.prototype.getProjectId = function (callback) {
  var self = this;

  if (this.projectId) {
    setImmediate(function () {
      callback(null, self.projectId);
    });

    return;
  }

  this.getAuthClient(function (err) {
    if (err) {
      callback(err);
      return;
    }

    callback(null, self.projectId);
  });
};

Auth.prototype.getToken = function (callback) {
  this.getAuthClient(function (err, client) {
    if (err) {
      callback(err);
      return;
    }

    client.getAccessToken(callback);
  });
};

Auth.prototype.isAppEngine = function (callback) {
  var self = this;

  setImmediate(function () {
    if (typeof self.environment.IS_APP_ENGINE === 'undefined') {
      self.environment.IS_APP_ENGINE =
        !!(process.env.GAE_SERVICE || process.env.GAE_MODULE_NAME);
    }

    callback(null, self.environment.IS_APP_ENGINE);
  });
};

Auth.prototype.isCloudFunction = function (callback) {
  var self = this;

  setImmediate(function () {
    if (typeof self.environment.IS_CLOUD_FUNCTION === 'undefined') {
      self.environment.IS_CLOUD_FUNCTION = !!process.env.FUNCTION_NAME;
    }

    callback(null, self.environment.IS_CLOUD_FUNCTION);
  });
};

Auth.prototype.isComputeEngine = function (callback) {
  var self = this;

  if (typeof this.environment.IS_COMPUTE_ENGINE !== 'undefined') {
    setImmediate(function () {
      callback(null, self.environment.IS_COMPUTE_ENGINE);
    });
    return;
  }

  request('http://metadata.google.internal', function (err, res) {
    self.environment.IS_COMPUTE_ENGINE =
      !err && res.headers['metadata-flavor'] === 'Google';

    callback(null, self.environment.IS_COMPUTE_ENGINE);
  });
};

Auth.prototype.isContainerEngine = function (callback) {
  var self = this;

  if (typeof this.environment.IS_CONTAINER_ENGINE !== 'undefined') {
    setImmediate(function () {
      callback(null, self.environment.IS_CONTAINER_ENGINE);
    });
    return;
  }

  gcpMetadata.instance('/attributes/cluster-name', function (err) {
    self.environment.IS_CONTAINER_ENGINE = !err;

    callback(null, self.environment.IS_CONTAINER_ENGINE);
  });
};

module.exports = Auth;
