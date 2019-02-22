import request from '../utils/request';
import axios from 'axios';

function parseMonths(datastoreConfig, selectedIndices) {
  let indices = '';

  selectedIndices.map(value => {
    indices += datastoreConfig.prefix + datastoreConfig.run_index + value + ',';
  });

  return indices;
}

export async function queryControllers(params) {
  const { datastoreConfig, selectedIndices } = params;

  const endpoint =
    datastoreConfig.elasticsearch +
    '/' +
    parseMonths(datastoreConfig, selectedIndices) +
    '/_search';

  return request(endpoint, {
    method: 'POST',
    body: {
      aggs: {
        controllers: {
          terms: {
            field: 'controller',
            size: 0,
            order: [{ runs: 'desc' }, { runs_preV1: 'desc' }],
          },
          aggs: {
            runs_preV1: {
              max: {
                field: 'run.start_run',
              },
            },
            runs: {
              max: {
                field: 'run.start',
              },
            },
          },
        },
      },
    },
  });
}

export async function queryResults(params) {
  const { datastoreConfig, selectedIndices, controller } = params;

  const endpoint =
    datastoreConfig.elasticsearch +
    '/' +
    parseMonths(datastoreConfig, selectedIndices) +
    '/_search';

  return request(endpoint, {
    method: 'POST',
    body: {
      fields: [
        'run.controller',
        'run.start',
        'run.start_run', // For pre-v1 run mapping version
        'run.end',
        'run.end_run', // For pre-v1 run mapping version
        'run.name',
        'run.config',
        'run.prefix',
        'run.id',
      ],
      sort: {
        'run.end': {
          order: 'desc',
          ignore_unmapped: true,
        },
      },
      query: {
        term: {
          'run.controller': controller,
        },
      },
      size: 5000,
    },
  });
  return request(endpoint);
}

export async function queryResult(params) {
  const { datastoreConfig, selectedIndices, result } = params;

  const endpoint =
    datastoreConfig.elasticsearch +
    '/' +
    parseMonths(datastoreConfig, selectedIndices) +
    '/_search?source=';

  return request(endpoint, {
    method: 'POST',
    body: {
      query: {
        match: {
          'run.name': result,
        },
      },
      sort: '_index',
    },
  });
}

export async function queryTocResult(params) {
  const { datastoreConfig, selectedIndices, id } = params;
  const endpoint =
    datastoreConfig.elasticsearch +
    '/' +
    parseMonths(datastoreConfig, selectedIndices) +
    '/_search?q=_parent:"' +
    id +
    '"';
  return request(endpoint);
}

export async function queryIterations(params) {
  const { datastoreConfig, selectedResults } = params;

  if (params.selectedResults === undefined) {
    console.log('queryIterations called without params.selectedResults defined.');
    return;
  }

  let iterationRequests = [];
  selectedResults.map(result => {
    const controller = result['run.controller'];
    iterationRequests.push(
      axios.get(
        datastoreConfig.results
          + '/incoming/'
          + (controller.includes('.')
             ? encodeURI(controller.slice(0, controller.indexOf('.')))
             : encodeURI(controller))
          + '/'
          + encodeURI(result['run.name'])
          + '/result.json'
      )
    );
  });

  return Promise.all(iterationRequests)
    .then(response => {
      let iterations = [];
      response.map((iteration, index) => {
        iterations.push({
          iterationData: iteration.data,
          controllerName: iteration.config.url.split('/')[4],
          resultName: iteration.config.url.split('/')[5],
          tableId: index,
        });
      })
      return iterations;
    })
    .catch(error => {
      if ((error.response !== undefined) && (error.response.status !== undefined)) {
        if (error.response.status == 404) {
          console.log('(404) Not Found (queryIterations): ' + error.request.responseURL);
          return [];
        }
        else {
          console.log(
            '(' + error.response.status + ') queryIterations: GET ' + error.request.responseURL + ' -- ' + error
          );
          throw error;
        }
      }
      else {
        console.log("queryIterations: " + error);
        throw error;
      }
    });
}
