const containsKey = (columns, item) => {
  var contains = false;
  for (var column in columns) {
    if (columns[column].key == item) {
      return true;
    }
    var keys = Object.keys(columns[column]);
    for (var key in keys) {
      if (keys[key] == 'children') {
        containsKey(columns[column].children, item);
      }
    }
  }
  return contains;
};

const containsTitle = (columns, item) => {
  var contains = false;
  for (var column in columns) {
    if (columns[column].title == item) {
      return true;
    }
    var keys = Object.keys(columns[column]);
    for (var key in keys) {
      if (keys[key] == 'children') {
        containsTitle(columns[column].children, item);
      }
    }
  }
  return contains;
};

const containsIteration = (columns, item) => {
  if (columns.children == undefined) {
    return false;
  }
  var contains = false;
  for (var column in columns.children) {
    if (columns.children[column].title == item) {
      return true;
    }
  }
  return contains;
};

const getColumnIndex = (columns, item) => {
  for (var column in columns) {
    if (columns[column].title == item) {
      return column;
    }
  }
};

export const parseIterationData = results => {
  var ports = [];
  var responseDataAll = [];
  var parsedResponseData = [];
  var configData = {};
  var selectedRowKeys = [];

  if (results == undefined) {
    // console.log('no results to parse');
    return {
      responseData: parsedResponseData,
      responseDataAll: responseDataAll,
      selectedRowKeys: selectedRowKeys,
      configData: configData,
      ports: ports,
    };
  }

  // console.log('parsing results');
  results.map(result => {
    let resultName = result.resultName;
    let controllerName = result.controllerName;
    let table = result.tableId;

    var responseData = [];
    var iterations = [];
    selectedRowKeys.push([]);

    var columns = [
      {
        title: '#',
        dataIndex: 'iteration_number',
        fixed: 'left',
        width: 50,
        key: 'iteration_number',
        sorter: (a, b) => a.iteration_number - b.iteration_number,
      },
      {
        title: 'Iteration Name',
        dataIndex: 'iteration_name',
        fixed: 'left',
        width: 150,
        key: 'iteration_name',
      },
    ];

    result = result['iterationData'];
    for (var iteration in result) {
      if (result[iteration].iteration_name.includes('fail')) {
        // console.log('Skipping iteration, ' + result[iteration].iteration_name);
        continue;
      }
      if (result[iteration].iteration_data.parameters.benchmark[0] == undefined) {
        // console.log(
        //   'Skipping iteration with no benchmakr parameters, ' + result[iteration].iteration_name
        // );
        continue;
      }
      var benchmark_params = result[iteration].iteration_data.parameters.benchmark[0];
      var iterationObject = {
        iteration_name: result[iteration].iteration_name,
        iteration_number: result[iteration].iteration_number,
        result_name: resultName,
        controller_name: controllerName,
        table: table,
      };
      var configObject = {};
      var keys = Object.keys(benchmark_params);
      for (var key in keys) {
        if (
          (keys[key] != 'uid') &
          (keys[key] != 'clients') &
          (keys[key] != 'servers') &
          (keys[key] != 'max_stddevpct')
        ) {
          if (!Object.keys(configData).includes(keys[key])) {
            configData[keys[key]] = [benchmark_params[keys[key]]];
          } else {
            if (!configData[keys[key]].includes(benchmark_params[keys[key]])) {
              configData[keys[key]].push(benchmark_params[keys[key]]);
            }
          }
          configObject[keys[key]] = benchmark_params[keys[key]];
        }
      }
      var iterationObject = Object.assign({}, iterationObject, configObject);
      for (var iterationType in result[iteration].iteration_data) {
        if (iterationType == 'parameters') {
          continue;
        }
        if (!containsTitle(columns, iterationType)) {
          columns.push({ title: iterationType });
        }
        var curr_iter_type = result[iteration].iteration_data[iterationType];
        for (var iterationNetwork in curr_iter_type) {
          var parentColumnIndex = getColumnIndex(columns, iterationType);
          var constructChildCol;
          if (!containsIteration(columns[parentColumnIndex], iterationNetwork)) {
            if (columns[parentColumnIndex]['children'] == undefined) {
              columns[parentColumnIndex]['children'] = [{ title: iterationNetwork }];
            } else {
              columns[parentColumnIndex]['children'].push({ title: iterationNetwork });
            }
            constructChildCol = true;
          } else {
            constructChildCol = false;
          }
          for (var iterationData in curr_iter_type[iterationNetwork]) {
            // console.log(
            //   '[iteration_name, iterationType, iterationNetwork, iterationData] = [ ' +
            //   result[iteration].iteration_name +
            //   ', ' +
            //   iterationType +
            //   ', ' +
            //   iterationNetwork +
            //   ', ' +
            //   iterationData +
            //   ' ]'
            // );
            var port_val = curr_iter_type[iterationNetwork][iterationData].server_port;
            if (port_val != undefined && !ports.includes(port_val)) {
              ports.push(port_val);
            }
            var columnTitle =
              'client_hostname:' +
              curr_iter_type[iterationNetwork][iterationData].client_hostname +
              '-server_hostname:' +
              curr_iter_type[iterationNetwork][iterationData].server_hostname +
              '-server_port:' +
              port_val;
            var _columnPrefix = iterationType + '-' + iterationNetwork + '-' + columnTitle + '-';
            var columnMean = _columnPrefix + 'mean';
            var columnStdDev = _columnPrefix + 'stddevpct';
            var columnSample = _columnPrefix + 'closestsample';
            if (constructChildCol) {
              if (columns[parentColumnIndex]['children'] == undefined) {
                var childColumnIndex = 0;
              } else {
                var childColumnIndex = getColumnIndex(
                  columns[parentColumnIndex].children,
                  iterationNetwork
                );
              }
              var child_column = columns[parentColumnIndex].children[childColumnIndex];
              if (!containsIteration(child_column, columnTitle)) {
                if (child_column['children'] == undefined) {
                  child_column['children'] = [{ title: columnTitle, dataIndex: columnTitle }];
                } else {
                  child_column['children'].push({ title: columnTitle });
                }
              }
              var dataChildColumnIndex = getColumnIndex(child_column['children'], columnTitle);
              if (dataChildColumnIndex == undefined) {
                dataChildColumnIndex = 0;
              }
              var data_column = child_column.children[dataChildColumnIndex];
              if (!containsKey(columns, columnMean)) {
                var _obj = {
                  title: 'mean',
                  dataIndex: columnMean,
                  key: columnMean,
                  sorter: (a, b) => a[columnMean] - b[columnMean],
                };
                if (data_column['children'] == undefined) {
                  data_column['children'] = [_obj];
                } else {
                  data_column['children'].push(_obj);
                }
              }
              if (!containsKey(columns, columnStdDev)) {
                var _obj = {
                  title: 'stddevpct',
                  dataIndex: columnStdDev,
                  key: columnStdDev,
                  sorter: (a, b) => a[columnStdDev] - b[columnStdDev],
                };
                if (data_column['children'] == undefined) {
                  data_column['children'] = [_obj];
                } else {
                  data_column['children'].push(_obj);
                }
              }
              if (!containsKey(columns, columnSample)) {
                var _obj = {
                  title: 'closest sample',
                  dataIndex: columnSample,
                  key: columnSample,
                  sorter: (a, b) => a[columnSample] - b[columnSample],
                  render: (text, record) => {
                    return <div>{text}</div>;
                  },
                };
                if (data_column['children'] == undefined) {
                  data_column['children'] = [_obj];
                } else {
                  data_column['children'].push(_obj);
                }
              }
            }
            iterationObject[columnMean] = curr_iter_type[iterationNetwork][iterationData].mean;
            iterationObject[columnStdDev] =
              curr_iter_type[iterationNetwork][iterationData].stddevpct;
            let closest_sample;
            if (curr_iter_type[iterationNetwork][iterationData]['closest sample'] == undefined) {
              closest_sample = curr_iter_type[iterationNetwork][iterationData]['closest_sample'];
            }
            else {
              closest_sample = curr_iter_type[iterationNetwork][iterationData]['closest sample'];
            }
            iterationObject[columnSample] = closest_sample;
            iterationObject['closest_sample'] = closest_sample;
          }
        }
      }

      iterations.push(iterationObject);
    }
    iterations.sort(function(a, b) {
      return a.iteration_number - b.iteration_number;
    });
    for (var iteration in iterations) {
      iterations[iteration]['key'] = iteration;
      responseDataAll.push(iterations[iteration]);
    }
    responseData['resultName'] = resultName;
    responseData['columns'] = columns;
    responseData['iterations'] = iterations;
    parsedResponseData.push(responseData);
  });

  // console.log('parsed results; ports.length = ' + ports.length);
  return {
    responseData: parsedResponseData,
    responseDataAll: responseDataAll,
    selectedRowKeys: selectedRowKeys,
    configData: configData,
    ports: ports,
  };
};
