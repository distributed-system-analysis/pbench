import _ from 'lodash';
import request from '../utils/request';
import { renameProp } from '../utils/utils';

function parseMonths(datastoreConfig, index, selectedIndices) {
  let indices = '';

  selectedIndices.forEach(value => {
    if (index === datastoreConfig.result_index) {
      indices += `${datastoreConfig.prefix + index + value}-*,`;
    } else {
      indices += `${datastoreConfig.prefix + index + value},`;
    }
  });

  return indices;
}

export async function queryControllers(params) {
  const { datastoreConfig, selectedIndices } = params;

  const endpoint = `${datastoreConfig.elasticsearch}/${parseMonths(
    datastoreConfig,
    datastoreConfig.run_index,
    selectedIndices
  )}/_search`;

  return request.post(endpoint, {
    data: {
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
    datastoreConfig.run_index,
    selectedIndices
  )}/_search`;

  return request.post(endpoint, {
    data: {
      fields: [
        '@metadata.controller_dir',
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
    datastoreConfig.run_index,
    selectedIndices
  )}/_search?source=`;

  return request.post(endpoint, {
    data: {
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
    datastoreConfig.run_index,
    selectedIndices
  )}/_search?q=_parent:"${id}"`;

  return request.post(endpoint);
}

export async function queryIterationSamples(params) {
  const { datastoreConfig, selectedIndices, selectedResults } = params;

  const endpoint = `${datastoreConfig.elasticsearch}/${parseMonths(
    datastoreConfig,
    datastoreConfig.result_index,
    selectedIndices
  )}/_search?scroll=1m`;

  const iterationSampleRequests = [];
  selectedResults.forEach(run => {
    iterationSampleRequests.push(
      request.post(endpoint, {
        data: {
          query: {
            filtered: {
              query: {
                multi_match: {
                  query: run.id,
                  fields: ['run.id'],
                },
              },
              filter: {
                term: {
                  _type: 'pbench-result-data-sample',
                },
              },
            },
          },
          aggs: {
            id: {
              terms: {
                field: 'run.id',
              },
              aggs: {
                type: {
                  terms: {
                    field: 'sample.measurement_type',
                  },
                  aggs: {
                    title: {
                      terms: {
                        field: 'sample.measurement_title',
                      },
                      aggs: {
                        uid: {
                          terms: {
                            field: 'sample.uid',
                          },
                        },
                      },
                    },
                  },
                },
              },
            },
            name: {
              terms: {
                field: 'run.name',
              },
            },
            controller: {
              terms: {
                field: 'run.controller',
              },
            },
          },
          size: 10000,
          sort: [
            {
              'iteration.number': {
                order: 'asc',
                unmapped_type: 'boolean',
              },
            },
          ],
        },
      })
    );
  });

  return Promise.all(iterationSampleRequests).then(iterations => {
    return iterations;
  });
}

export async function queryIterations(params) {
  const { datastoreConfig, selectedResults } = params;

  const iterationRequests = [];
  selectedResults.forEach(result => {
    let controllerDir = result['@metadata.controller_dir'];
    if (controllerDir === undefined) {
      controllerDir = result['run.controller'];
      controllerDir = controllerDir.includes('.')
        ? controllerDir.slice(0, controllerDir.indexOf('.'))
        : controllerDir;
    }
    iterationRequests.push(
      request.get(
        `${datastoreConfig.results}/incoming/${encodeURI(controllerDir)}/${encodeURI(
          result['run.name']
        )}/result.json`,
        { getResponse: true }
      )
    );
  });

  return Promise.all(iterationRequests).then(response => {
    const iterations = [];
    response.forEach((iteration, index) => {
      iterations.push({
        iterationData: iteration.data,
        controllerName: iteration.response.url.split('/')[4],
        resultName: iteration.response.url.split('/')[5],
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
          request.get(
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
          const iterationTypes = Object.keys(args[responseCount]);
          Object.keys(iterationTypes).forEach(iterationTest => {
            if (
              Object.keys(args[responseCount][iterationTypes[iterationTest]]).includes(
                primaryMetric
              )
            ) {
              const hosts = args[responseCount][iterationTypes[iterationTest]][primaryMetric];
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
