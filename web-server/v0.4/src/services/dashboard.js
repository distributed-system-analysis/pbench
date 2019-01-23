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
            order: {
              runs: 'desc',
            },
          },
          aggs: {
            runs: {
              min: {
                field: 'run.start_run',
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
        'run.start_run',
        'run.end_run',
        'run.name',
        'run.config',
        'run.prefix',
      ],
      sort: {
        'run.end_run': {
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

export async function queryIterations(params) {
  const { datastoreConfig, selectedResults } = params;

  let iterationRequests = [];
  if (typeof params.selectedResults != undefined) {
    selectedResults.map(result => {
      if (result.controller.includes('.')) {
        axios.get(
          datastoreConfig.results +
            '/results/' +
            encodeURI(result.controller.slice(0, result.controller.indexOf('.'))) +
            (result['run.prefix'] != null ? '/' + result['run.prefix'] : '') +
            '/' +
            encodeURI(result['run.name']) +
            '/result.json'
        );
      }
      iterationRequests.push(
        axios.get(
          datastoreConfig.results +
            '/results/' +
            encodeURI(result.controller.slice(0, result.controller.indexOf('.'))) +
            (result['run.prefix'] != null ? '/' + result['run.prefix'] : '') +
            '/' +
            encodeURI(result['run.name']) +
            '/result.json'
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
        });

        return iterations;
      })
      .catch(error => {
        console.log(error);
      });
  }
}
