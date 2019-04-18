import _ from 'lodash';
import { Icon } from 'antd';
import React from 'react';

export const parseIterationData = results => {
  const iterations = [];
  const iterationParams = {};
  const iterationPorts = [];
  const selectedIterationKeys = [];

  results.forEach(result => {
    const columns = [
      {
        title: 'Iteration Name',
        dataIndex: 'iteration_name',
        width: 150,
        key: 'iteration_name',
      },
    ];
    const parsedResponse = {
      iterations: [],
      columns: [],
      resultName: '',
    };
    selectedIterationKeys.push([]);

    result.iterationData.forEach((iteration, index) => {
      let iterationMetadata = {
        iteration_name: iteration.iteration_name,
        iteration_number: iteration.iteration_number,
        result_name: result.resultName,
        controller_name: result.controllerName,
        table: result.tableId,
        key: index,
      };
      const iterationConfig = iteration.iteration_data.parameters.benchmark
        ? Object.entries(iteration.iteration_data.parameters.benchmark[0])
        : [];
      const blacklistedParams = ['uid', 'clients', 'servers', 'max_stddevpct'];
      iterationConfig.forEach(([parameter, value]) => {
        if (!blacklistedParams.includes(parameter)) {
          if (iterationParams[parameter]) {
            if (!iterationParams[parameter].includes(value)) {
              iterationParams[parameter].push(value);
            }
          } else {
            iterationParams[parameter] = [value];
          }
        }
      });
      iterationMetadata = {
        ...iterationMetadata,
        ...iteration.iteration_data.parameters.benchmark[0],
      };

      if (iteration.iteration_name.includes('fail') || !iterationConfig) {
        return;
      }

      Object.entries(iteration.iteration_data).forEach(([iterationType, iterationNetworkData]) => {
        let iterationTypeColumnIndex = _.findIndex(columns, { title: iterationType });
        if (iterationType !== 'parameters' && iterationTypeColumnIndex) {
          if (!_.includes(columns[iterationTypeColumnIndex], iterationType)) {
            columns.push({ title: iterationType });
          }
        } else {
          return;
        }

        Object.entries(iterationNetworkData).forEach(([iterationNetwork, iterationData]) => {
          // Find iteration type column and create or append iteration network child entry
          iterationTypeColumnIndex = _.findIndex(columns, { title: iterationType });
          if (_.has(columns[iterationTypeColumnIndex], 'children')) {
            if (!_.some(columns[iterationTypeColumnIndex].children, { title: iterationNetwork })) {
              columns[iterationTypeColumnIndex].children.push({ title: iterationNetwork });
            }
          } else {
            columns[iterationTypeColumnIndex].children = [{ title: iterationNetwork }];
          }

          iterationData.forEach(hostMetadata => {
            const columnHost = `client_hostname:${hostMetadata.client_hostname}-server_hostname:${
              hostMetadata.server_hostname
            }-server_port:${hostMetadata.server_port}`;
            const columnPrefix = `${iterationType}-${iterationNetwork}-${columnHost}`;
            const columnMean = `${columnPrefix}-mean`;
            const columnStdDev = `${columnPrefix}-stddevpct`;
            const columnSample = `${columnPrefix}-closestsample`;

            // Find iteration network column and create or append iteration column child entry
            const iterationTypeColumn = columns[iterationTypeColumnIndex].children;
            const iterationNetworkColumnIndex = _.findIndex(iterationTypeColumn, {
              title: iterationNetwork,
            });
            if (!iterationPorts.includes(columnHost)) {
              iterationPorts.push(columnHost);
            }
            if (_.has(iterationTypeColumn[iterationNetworkColumnIndex], 'children')) {
              if (
                !_.some(iterationTypeColumn[iterationNetworkColumnIndex].children, {
                  dataIndex: columnPrefix,
                })
              ) {
                iterationTypeColumn[iterationNetworkColumnIndex].children.push({
                  title: columnHost,
                  dataIndex: columnPrefix,
                });
              }
            } else {
              iterationTypeColumn[iterationNetworkColumnIndex].children = [
                { title: columnHost, dataIndex: columnPrefix },
              ];
            }

            const dataIndexColumn = iterationTypeColumn[iterationNetworkColumnIndex].children;
            const dataIndexColumnIndex = _.findIndex(
              columns[iterationTypeColumnIndex].children[iterationNetworkColumnIndex].children,
              { title: columnHost }
            );
            const columnMeanData = {
              title: 'mean',
              dataIndex: columnMean,
              key: columnMean,
              sorter: (a, b) => a[columnMean] - b[columnMean],
            };
            const columnStdDevData = {
              title: 'stddevpct',
              dataIndex: columnStdDev,
              key: columnStdDev,
              sorter: (a, b) => a[columnStdDev] - b[columnStdDev],
            };
            const columnSampleData = {
              title: 'closest sample',
              dataIndex: columnSample,
              key: columnSample,
              sorter: (a, b) => a[columnSample] - b[columnSample],
            };

            if (_.has(dataIndexColumn[dataIndexColumnIndex], 'children')) {
              if (
                !_.some(dataIndexColumn[dataIndexColumnIndex].children, { dataIndex: columnMean })
              ) {
                dataIndexColumn[dataIndexColumnIndex].children.push(columnMeanData);
              }
              if (
                !_.some(dataIndexColumn[dataIndexColumnIndex].children, { dataIndex: columnStdDev })
              ) {
                dataIndexColumn[dataIndexColumnIndex].children.push(columnStdDevData);
              }
              if (
                !_.some(dataIndexColumn[dataIndexColumnIndex].children, { dataIndex: columnSample })
              ) {
                dataIndexColumn[dataIndexColumnIndex].children.push(columnSampleData);
              }
            } else {
              dataIndexColumn[dataIndexColumnIndex].children = [
                columnMeanData,
                columnStdDevData,
                columnSampleData,
              ];
            }
            iterationMetadata[columnMean] = hostMetadata.mean;
            iterationMetadata[columnStdDev] = hostMetadata.stddevpct;
            const iterationClosestSample =
              typeof hostMetadata.closest_sample !== 'undefined'
                ? hostMetadata.closest_sample
                : hostMetadata['closest sample'];
            iterationMetadata[columnSample] = iterationClosestSample;
            iterationMetadata.closest_sample = iterationClosestSample;
          });
        });
      });
      parsedResponse.iterations.push(iterationMetadata);
    });
    parsedResponse.iterations.sort((a, b) => a.iteration_number - b.iteration_number);
    parsedResponse.resultName = result.resultName;
    parsedResponse.controllerName = result.controllerName;
    parsedResponse.columns = columns;
    iterations.push(parsedResponse);
  });

  return {
    iterations,
    selectedIterationKeys,
    iterationParams,
    iterationPorts,
  };
};

const cloneResultsData = results => {
  const resultsCopy = [];

  results.forEach((result, index) => {
    resultsCopy[index] = {};
    resultsCopy[index].columns = _.cloneDeep(result.columns);
    resultsCopy[index].iterations = _.cloneDeep(result.iterations);
    resultsCopy[index].resultName = result.resultName;
    resultsCopy[index].controllerName = result.controllerName;
  });

  return resultsCopy;
};

const removeColumnKey = (column, columns, ports, index) => {
  if (column && column.title && column.title.includes('port')) {
    ports.forEach(port => {
      if (column.title !== port) {
        columns.splice(index, 1);
      }
    });
  }
  if (column && column.children && column.children.length > 0) {
    column.children.forEach((childColumn, childIndex) => {
      removeColumnKey(childColumn, column.children, ports, childIndex);
    });
  }
};

const filterColumns = (columns, ports) => {
  const filteredColumn = [];
  columns.forEach((column, index) => {
    removeColumnKey(column, columns, ports, index);
    filteredColumn.push(column);
  });
  return filteredColumn;
};

export const filterIterations = (results, selectedParams, selectedPorts) => {
  const resultsCopy = cloneResultsData(results);

  resultsCopy.forEach((result, index) => {
    const filteredColumns = filterColumns(result.columns, selectedPorts);

    const filteredIterations = [];
    result.iterations.forEach(iteration => {
      if (_.isMatch(iteration, selectedParams)) {
        filteredIterations.push(iteration);
      }
    });
    resultsCopy[index].columns = filteredColumns;
    resultsCopy[index].iterations = filteredIterations;
  });

  return resultsCopy;
};

export const filterIterationColumns = (results, selectedPorts) => {
  const resultsCopy = cloneResultsData(results);

  resultsCopy.forEach((result, index) => {
    selectedPorts.forEach(port => {
      resultsCopy[index].columns = filterColumns(result.columns, port);
    });
  });

  return resultsCopy;
};

export const parseClusteredIterations = (clusteredIterations, clusterLabels, selectedConfig) => {
  const clusteredGraphData = [];
  const graphKeys = [];
  const tableData = [];
  let maxIterationLength = 0;

  Object.keys(clusteredIterations).forEach(primaryMetric => {
    clusteredGraphData[primaryMetric] = [];
    graphKeys[primaryMetric] = [];
    tableData[primaryMetric] = [];
    let maxClusterLength = 0;
    Object.keys(clusteredIterations[primaryMetric]).forEach(cluster => {
      const clusterObject = { cluster };
      const meanValues = [];
      Object.keys(clusteredIterations[primaryMetric][cluster]).forEach(iteration => {
        clusterObject[iteration] =
          clusteredIterations[primaryMetric][cluster][iteration][
            Object.keys(clusteredIterations[primaryMetric][cluster][iteration]).find(key => {
              if (key.includes('all') && key.includes('mean')) {
                return key;
              }
              return false;
            })
          ];
        meanValues.push(clusterObject[iteration]);
        let percentage = 0;
        if (iteration !== 0) {
          percentage =
            ((clusterObject[iteration] - clusterObject[0]) /
              ((clusterObject[iteration] + clusterObject[0]) / 2)) *
            100;
        }
        clusterObject[`percent${iteration}`] = percentage.toFixed(1);
        if (meanValues.length > maxIterationLength) {
          maxIterationLength = meanValues.length;
        }
        clusterObject[`name${iteration}`] =
          clusteredIterations[primaryMetric][cluster][iteration].iteration_name;
      });
      clusteredGraphData[primaryMetric].push(clusterObject);
      const clusterItems = Object.keys(clusterObject).length - 1;
      if (clusterItems > maxClusterLength) {
        maxClusterLength = clusterItems;
      }
      tableData[primaryMetric].push({
        key: cluster,
        clusterID: cluster,
        cluster: clusterLabels[primaryMetric][cluster],
        primaryMetric,
        length: clusterItems,
      });
    });
    for (let i = 0; i < maxClusterLength; i += 1) {
      graphKeys[primaryMetric].push(i);
    }
  });
  return {
    tableData,
    graphKeys,
    clusteredGraphData,
    maxIterationLength,
    clusteredIterations,
    selectedConfig,
  };
};

export const groupClusters = (array, cluster, f) => {
  const groups = {};

  array.forEach(o => {
    const group = f(o).join('-');
    groups[group] = groups[group] || [];
    groups[group].push(o);
  });

  return {
    clusterLabels: Object.keys(groups),
    cluster: Object.keys(groups).map(group => groups[group]),
  };
};

export const generateIterationClusters = (config, iterations) => {
  let primaryMetricIterations = [];
  let clusteredIterations = [];
  const clusterLabels = [];
  const selectedConfig = config;

  primaryMetricIterations = _.mapValues(_.groupBy(iterations, 'primary_metric'), clist =>
    clist.map(iteration => _.omit(iteration, 'primary_metric'))
  );

  Object.keys(primaryMetricIterations).forEach(cluster => {
    clusteredIterations = [];
    if (typeof config === 'object' && config.length > 0) {
      clusteredIterations = groupClusters(primaryMetricIterations[cluster], cluster, item => {
        const configData = [];
        config.forEach(filter => {
          configData.push(item[filter]);
        });
        return configData;
      });
    } else {
      clusteredIterations = _.mapValues(
        _.groupBy(primaryMetricIterations[cluster], config),
        clist => clist.map(iteration => _.omit(iteration, config))
      );
    }
    primaryMetricIterations[cluster] = clusteredIterations.cluster;
    clusterLabels[cluster] = clusteredIterations.clusterLabels;
  });

  return parseClusteredIterations(primaryMetricIterations, clusterLabels, selectedConfig);
};

export const getComparisonColumn = maxIterationLength => {
  const children = [];
  for (let i = 0; i < maxIterationLength; i += 1) {
    children.push({
      title: `Iteration - ${i}`,
      dataIndex: `Iteration-${i}`,
      key: `Iteration${i}`,
      children: [
        {
          title: 'Name',
          dataIndex: `name${i}`,
          key: `name${i}`,
          width: 250,
          render: text => {
            if (text === undefined) {
              return {
                props: {
                  style: { background: '#e8e8e8' },
                },
              };
            }
            return <div>{text}</div>;
          },
        },
        {
          title: 'Mean',
          dataIndex: i,
          key: `mean${i}`,
          width: 250,
          render: text => {
            if (text === undefined) {
              return {
                props: {
                  style: { background: '#e8e8e8' },
                },
              };
            }
            return <div>{text}</div>;
          },
        },
        {
          title: 'Percent',
          dataIndex: `percent${i}`,
          key: `percent${i}`,
          width: 0,
          render: text => {
            if (text > 0) {
              return (
                <div style={{ textAlign: 'right' }}>
                  {`${text}%`}
                  <Icon
                    type="caret-up"
                    theme="filled"
                    style={{ marginLeft: '3%', color: 'green' }}
                  />
                </div>
              );
            }
            if (text < 0) {
              return (
                <div style={{ textAlign: 'right' }}>
                  {`${Math.abs(text)}%`}
                  <Icon
                    type="caret-down"
                    theme="filled"
                    style={{ marginLeft: '3%', color: 'red' }}
                  />
                </div>
              );
            }
            if (text === undefined) {
              return {
                props: {
                  style: { background: '#e8e8e8' },
                },
              };
            }
            return (
              <div>
                <Icon type="dash" style={{ color: 'red' }} />
              </div>
            );
          },
        },
      ],
    });
  }
  const column = [
    {
      title: 'Cluster',
      dataIndex: 'cluster',
      key: 'cluster',
      width: 150,
      fixed: 'left',
      render: text => `cluster - ${text}`,
    },
    {
      title: 'Iteration',
      children,
    },
  ];
  return column;
};
