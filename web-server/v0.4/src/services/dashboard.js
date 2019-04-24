import axios from 'axios';
import _ from 'lodash';
import request from '../utils/request';
import { renameProp } from '../utils/utils';

function parseMonths(datastoreConfig, selectedIndices) {
  let indices = '';

  selectedIndices.forEach(value => {
    indices += `${datastoreConfig.prefix + datastoreConfig.run_index + value},`;
  });

  return indices;
}

export async function queryControllers(params) {
  const { datastoreConfig, selectedIndices } = params;

  const endpoint = `${datastoreConfig.elasticsearch}/${parseMonths(
    datastoreConfig,
    selectedIndices
  )}/_search`;

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

  const endpoint = `${datastoreConfig.elasticsearch}/${parseMonths(
    datastoreConfig,
    selectedIndices
  )}/_search`;

  return request(endpoint, {
    method: 'POST',
    body: {
      fields: [
        '@metadata.controllerDir',
        '@metadata.satellite',
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
          'run.controller': controller[0],
        },
      },
      size: 5000,
    },
  });
}

export async function queryResult(params) {
  const { datastoreConfig, selectedIndices, result } = params;

  const endpoint = `${datastoreConfig.elasticsearch}/${parseMonths(
    datastoreConfig,
    selectedIndices
  )}/_search?source=`;

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

  const endpoint = `${datastoreConfig.elasticsearch}/${parseMonths(
    datastoreConfig,
    selectedIndices
  )}/_search?q=_parent:"${id}"`;

  return request(endpoint);
}

export async function queryIterations(params) {
  const { datastoreConfig, selectedResults } = params;

  const iterationRequests = [];
  selectedResults.forEach(result => {
    let controllerDir = result['@metadata.controllerDir'];
    if (controllerDir === undefined) {
      controllerDir = result['run.controller'];
      controllerDir = controllerDir.includes('.')
        ? controllerDir.slice(0, controllerDir.indexOf('.'))
        : controllerDir;
    }
    iterationRequests.push(
      axios.get(
        `${datastoreConfig.results}/incoming/${encodeURI(controllerDir)}/${encodeURI(
          result['run.name']
        )}/result.json`
      )
    );
  });

  return Promise.all(iterationRequests).then(response => {
    const iterations = [];
    response.forEach((iteration, index) => {
      iterations.push({
        iterationData: iteration.data,
        controllerName: iteration.config.url.split('/')[4],
        resultName: iteration.config.url.split('/')[5],
        tableId: index,
      });
    });
    return iterations;
  });
}

export async function queryTimeseriesData(params) {
  const { datastoreConfig, clusteredIterations } = params;
  const iterationRequests = [];

  Object.keys(clusteredIterations).forEach(primaryMetric => {
    Object.keys(clusteredIterations[primaryMetric]).forEach(cluster => {
      Object.keys(clusteredIterations[primaryMetric][cluster]).forEach(iteration => {
        iterationRequests.push(
          axios.get(
            `${datastoreConfig.results}/incoming/${encodeURIComponent(
              clusteredIterations[primaryMetric][cluster][iteration].controller_name
            )}/${encodeURIComponent(
              clusteredIterations[primaryMetric][cluster][iteration].result_name
            )}/${encodeURIComponent(
              clusteredIterations[primaryMetric][cluster][iteration].iteration_number
            )}-${encodeURIComponent(
              clusteredIterations[primaryMetric][cluster][iteration].iteration_name
            )}/sample${encodeURIComponent(
              clusteredIterations[primaryMetric][cluster][iteration].closest_sample
            )}/result.json`
          )
        );
      });
    });
  });

  return Promise.all(iterationRequests).then(args => {
    const timeseriesData = [];
    const timeseriesDropdown = [];
    const timeseriesDropdownSelected = [];
    let responseCount = 0;

    Object.keys(clusteredIterations).forEach(primaryMetric => {
      timeseriesData[primaryMetric] = [];
      Object.keys(clusteredIterations[primaryMetric]).forEach(cluster => {
        timeseriesData[primaryMetric][cluster] = [];
        let iterationTimeseriesData = [];
        const timeseriesLabels = ['time'];
        Object.keys(clusteredIterations[primaryMetric][cluster]).forEach(iteration => {
          const iterationTypes = Object.keys(args[responseCount].data);
          Object.keys(iterationTypes).forEach(iterationTest => {
            if (
              Object.keys(args[responseCount].data[iterationTypes[iterationTest]]).includes(
                primaryMetric
              )
            ) {
              const hosts = args[responseCount].data[iterationTypes[iterationTest]][primaryMetric];
              Object.keys(hosts).forEach(host => {
                if (hosts[host].client_hostname === 'all') {
                  Object.keys(hosts[host].timeseries).forEach(item => {
                    hosts[host].timeseries[item] = renameProp(
                      'date',
                      'x',
                      hosts[host].timeseries[item]
                    );
                    hosts[host].timeseries[item] = renameProp(
                      'value',
                      `y${parseInt(iteration, 10) + 1}`,
                      hosts[host].timeseries[item]
                    );
                  });
                  timeseriesLabels.push(
                    `${clusteredIterations[primaryMetric][cluster][iteration].result_name}-${
                      clusteredIterations[primaryMetric][cluster][iteration].iteration_name
                    }`
                  );
                  iterationTimeseriesData = _.merge(
                    iterationTimeseriesData,
                    hosts[host].timeseries
                  );
                  responseCount += 1;
                }
              });
            }
          });
        });
        const timeLabel = timeseriesLabels.splice(0, 1)[0];
        timeseriesLabels.splice(1, 0, timeLabel);
        timeseriesData[primaryMetric][cluster].push({
          data_series_names: timeseriesLabels,
          data: iterationTimeseriesData.map(Object.values),
          x_axis_series: 'time',
        });
      });
    });
    Object.keys(timeseriesData).forEach(primaryMetric => {
      timeseriesDropdownSelected[primaryMetric] = 0;
      timeseriesDropdown[primaryMetric] = Object.keys(timeseriesData[primaryMetric]);
    });
    return {
      timeseriesData,
      timeseriesDropdownSelected,
      timeseriesDropdown,
    };
  });
}
