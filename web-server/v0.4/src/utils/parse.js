/* eslint-disable no-param-reassign */
import _ from 'lodash';
import { Icon } from 'antd';
import React from 'react';

export const filterIterations = (results, selectedParams) => {
  const resultsCopy = _.cloneDeep(results);
  Object.entries(resultsCopy).forEach(([runId, result]) => {
    Object.entries(result.iterations).forEach(([iterationId, iteration]) => {
      const match = _.isMatch(
        iteration[`sample${iteration.closest_sample}`][
          'client_hostname:all-server_hostname:all-server_port:all'
        ],
        selectedParams
      );
      if (match === false) {
        delete resultsCopy[runId].iterations[iterationId];
      }
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
              if (key.includes('all') && key.includes('mean') && key.includes(primaryMetric)) {
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
