import request from '../utils/request';

/**
 * This service references the node environment for retrieval of 
 * the API config file. Node specifies two types of environments
 * depending on how the dashboard has been run: 
 * 
 * `development` - the dashboard is referencing `dev.config.json`
 * and has been executed from the root directory using the `start`
 * script. 
 * 
 * `production` - the dashboard has been bundled to minimized
 * js, css, and html files using the `build` script and is 
 * deployed on a web server.
 */
export async function queryDatastoreConfig() {
  let configEndpoint = '';
  let environment = process.env || 'development';
  
  switch(environment) {
    case 'development':
      configEndpoint = 'http://localhost:8000/dev.config.json'
      break
    case 'production':
      // Note that window.location.pathname should already have a trailing slash.
      configEndpoint = window.location.pathname + 'config.json'
      break
  }

  return request(configEndpoint, {
    method: 'GET',
  });
}

export async function queryMonthIndices(params) {
  const { datastoreConfig } = params;

  const endpoint = datastoreConfig.elasticsearch + '/_cat/indices?format=json&pretty=true';

  return request(endpoint, {
    method: 'GET',
  });
}
