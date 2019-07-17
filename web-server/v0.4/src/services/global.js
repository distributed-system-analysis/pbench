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
  const environment = process.env || 'development';

  if (environment === 'development') {
    configEndpoint = '/dev/datastoreConfig';
  } else {
    configEndpoint = '/dashboard/config.json';
  }

  return request.get(configEndpoint);
}

export async function queryMonthIndices(params) {
  const { datastoreConfig } = params;

  const endpoint = `${datastoreConfig.elasticsearch}/_cat/indices?format=json&pretty=true`;

  return request.get(endpoint);
}

export async function querySaveSharedConfig(params) {
  const { stringProp, description, datastoreConfig } = params;
  return request.post(datastoreConfig.graphql, {
    data: {
      query: `
            mutation($config: String!, $description: String!) {
              createUrl(data: {config: $config, description: $description}) {
                id
                config
                description
              }
            }       
          `,
      variables: {
        config: stringProp,
        description,
      },
    },
  });
}
