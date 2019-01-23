import request from '../utils/request';

export async function queryDatastoreConfig() {
  // Note that window.location.pathname should have a trailing slash already.
  return request('http://localhost:8000/dev.config.json', {
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
