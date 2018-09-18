import request from '../utils/request';

export async function queryDatastoreConfig() {
  // Note that window.location.pathname should have a trailing slash already.
  return request(window.location.pathname + 'config.json', {
    method: 'GET',
  });
}
