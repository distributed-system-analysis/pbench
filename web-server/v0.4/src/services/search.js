import request from '../utils/request';

export async function queryIndexMapping(params) {
  const { datastoreConfig, indices } = params;

  const endpoint = datastoreConfig.elasticsearch + '/' + datastoreConfig.prefix + datastoreConfig.run_index + indices[0] + '/_mappings';

  return request(endpoint, {
    method: 'GET'
  });
}

export async function searchQuery(params) {
  const { datastoreConfig, selectedFields, selectedIndices, query } = params;

  let indices = "";
  selectedIndices.map((value) => {
    indices += datastoreConfig.prefix + datastoreConfig.run_index + value + ",";
  })

  const endpoint = datastoreConfig.elasticsearch + '/' + indices + '/_search';
  let searchQuery = "_type:pbench-run AND (";

  selectedFields.map((field, i) => {
    if (i < selectedFields.length - 1) {
      searchQuery = searchQuery.concat(field + ":*" + query + "* OR ");
    } else {
      searchQuery = searchQuery.concat(field + ":*" + query + "*)");
    }
  });

  return request(endpoint, {
    method: 'POST',
    body: {
      query: {
          query_string: {
              analyze_wildcard: true,
              query: searchQuery,
          },
      },
      size: 1000,
    },
  });
}