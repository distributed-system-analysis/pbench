import request from '../utils/request';
import axios from 'axios';

export async function queryControllers(params) {
  const { datastoreConfig } = params;

  const endpoint = datastoreConfig.elasticsearch + '/' + datastoreConfig.run_index + '/_search';

  return request(endpoint, {
    method: 'POST',
    body: {
      "aggs": {
        "run_hosts": {
          "terms": {
            "field": "run.host"
          }
        }
      }
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

export async function queryIterations(params) {
  const { datastoreConfig, selectedResults } = params;

  const endpoint =
    datastoreConfig.elasticsearch + '/' + datastoreConfig.run_index +  '/_search';

  let iterationRequests = [];
  if (typeof params.selectedResults != undefined) {
    selectedResults.map(result => {
      iterationRequests.push(
        axios.post(endpoint, {
          "query" : {
              "bool": {
                "filter": [
                  { "term":  { "run.id": result.result }}
                ]
              }
            }        
        }))
    })

    return Promise.all(iterationRequests)
      .then(response => {
        let iterations = [];
        response.map((iteration, index) => {
          iterations.push({
            iterationData: iteration.data,
            controllerName: JSON.parse(iteration.config.data).query.bool.filter[0].term["run.id"],
            resultName: JSON.parse(iteration.config.data).query.bool.filter[0].term["run.id"],
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