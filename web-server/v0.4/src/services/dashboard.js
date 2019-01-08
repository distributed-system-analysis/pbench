import request from '../utils/request';
import axios from 'axios';

export async function queryControllers(params) {
  const { datastoreConfig } = params;

  const endpoint = datastoreConfig.elasticsearch + '/' + datastoreConfig.run_index + '/_search';

  return request(endpoint, {
    method: 'POST',
    body: {
      aggs: {
        run_hosts: {
          terms: {
            field: 'run.host',
          },
        },
      },
    },
  });
}

export async function queryResults(params) {
  const { datastoreConfig, controller } = params;

  const endpoint =
    datastoreConfig.elasticsearch + '/' + datastoreConfig.run_index +  '/_search';

  return request(endpoint, {
    method: 'POST',
    body: {
      "query" : {
        "bool": {
          "filter": [
            { "term":  { "run.host": controller }}
          ]
        }
      }, "_source": [ "run.id", "run.bench" ]
    }
  });
}

export async function queryResult(params) {
  const { datastoreConfig, startMonth, endMonth, result } = params;

  const endpoint =
    datastoreConfig.elasticsearch +
    parseMonths(datastoreConfig, startMonth, endMonth) +
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
          datastoreConfig.production +
            '/results/' +
            encodeURI(result.controller.slice(0, result.controller.indexOf('.'))) +
            '/' +
            encodeURI(result.result) +
            '/result.json'
        );
      }
      iterationRequests.push(
        axios.get(
          datastoreConfig.production +
            '/results/' +
            encodeURI(result.controller.slice(0, result.controller.indexOf('.'))) +
            '/' +
            encodeURI(result.result) +
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