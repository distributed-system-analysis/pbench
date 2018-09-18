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
}

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
}

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
}

const getColumnIndex = (columns, item) => {
  for (var column in columns) {
    if (columns[column].title == item) {
      return column;
    }
  }
}

export const parseIterationData = (results) => {
    var ports = [];
    var configData = [];
    var responseDataAll = [];
    var parsedResponseData = [];
    var configCategories = {};
    var selectedRowKeys = [];

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

      result = result["iterationData"];
      for (var iteration in result) {
        if (!result[iteration].iteration_name.includes('fail')) {
          var iterationObject = {
            iteration_name: result[iteration].iteration_name,
            iteration_number: result[iteration].iteration_number,
            result_name: resultName,
            controller_name: controllerName,
            table: table,
          };
          var configObject = {};
          var keys = [];
          if (result[iteration].iteration_data.parameters.benchmark[0] != undefined) {
            var keys = Object.keys(result[iteration].iteration_data.parameters.benchmark[0]);
            for (var key in keys) {
              if (
                (keys[key] != 'uid') &
                (keys[key] != 'clients') &
                (keys[key] != 'servers') &
                (keys[key] != 'max_stddevpct')
              ) {
                if (!Object.keys(configCategories).includes(keys[key])) {
                  var obj = {};
                  configCategories[keys[key]] = [
                    result[iteration].iteration_data.parameters.benchmark[0][keys[key]],
                  ];
                } else {
                  if (
                    !configCategories[keys[key]].includes(
                      result[iteration].iteration_data.parameters.benchmark[0][keys[key]]
                    )
                  ) {
                    configCategories[keys[key]].push(
                      result[iteration].iteration_data.parameters.benchmark[0][keys[key]]
                    );
                  }
                }
                configObject[keys[key]] =
                  result[iteration].iteration_data.parameters.benchmark[0][keys[key]];
              }
            }
          }
          var iterationObject = Object.assign({}, iterationObject, configObject);
          for (var iterationType in result[iteration].iteration_data) {
            if (iterationType != 'parameters') {
              if (!containsTitle(columns, iterationType)) {
                columns.push({ title: iterationType });
              }
              for (var iterationNetwork in result[iteration].iteration_data[iterationType]) {
                var parentColumnIndex = getColumnIndex(columns, iterationType);
                if (!containsIteration(columns[parentColumnIndex], iterationNetwork)) {
                  if (columns[parentColumnIndex]['children'] == undefined) {
                    columns[parentColumnIndex]['children'] = [{ title: iterationNetwork }];
                  } else {
                    columns[parentColumnIndex]['children'].push({ title: iterationNetwork });
                  }
                  for (var iterationData in result[iteration].iteration_data[iterationType][
                    iterationNetwork
                  ]) {
                    var columnTitle =
                      'client_hostname:' +
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].client_hostname +
                      '-server_hostname:' +
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].server_hostname +
                      '-server_port:' +
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].server_port;
                    if (columns[parentColumnIndex]['children'] == undefined) {
                      var childColumnIndex = 0;
                    } else {
                      var childColumnIndex = getColumnIndex(
                        columns[parentColumnIndex].children,
                        iterationNetwork
                      );
                    }
                    if (
                      !containsIteration(
                        columns[parentColumnIndex].children[childColumnIndex],
                        columnTitle
                      )
                    ) {
                      if (
                        columns[parentColumnIndex].children[childColumnIndex]['children'] == undefined
                      ) {
                        columns[parentColumnIndex].children[childColumnIndex]['children'] = [
                          { title: columnTitle, dataIndex: columnTitle },
                        ];
                      } else {
                        columns[parentColumnIndex].children[childColumnIndex]['children'].push({
                          title: columnTitle,
                        });
                      }
                      var columnValue = columnTitle.split(':')[3];
                      if (!ports.includes(columnValue)) {
                        ports.push(columnValue);
                      }
                      var columnMean =
                        iterationType + '-' + iterationNetwork + '-' + columnTitle + '-' + 'mean';
                      var columnStdDev =
                        iterationType +
                        '-' +
                        iterationNetwork +
                        '-' +
                        columnTitle +
                        '-' +
                        'stddevpct';
                      var columnSample =
                        iterationType +
                        '-' +
                        iterationNetwork +
                        '-' +
                        columnTitle +
                        '-' +
                        'closestsample';
                      var dataChildColumnIndex = getColumnIndex(
                        columns[parentColumnIndex].children[childColumnIndex]['children'],
                        columnTitle
                      );
                      if (dataChildColumnIndex == undefined) {
                        dataChildColumnIndex = 0;
                      }
                      if (!containsKey(columns, columnMean)) {
                        if (
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'] == undefined
                        ) {
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'] = [
                            {
                              title: 'mean',
                              dataIndex: columnMean,
                              key: columnMean,
                              sorter: (a, b) => a[columnMean] - b[columnMean],
                            },
                          ];
                          iterationObject[columnMean] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ].mean;
                        } else {
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'].push({
                            title: 'mean',
                            dataIndex: columnMean,
                            key: columnMean,
                            sorter: (a, b) => a[columnMean] - b[columnMean],
                          });
                          iterationObject[columnMean] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ].mean;
                        }
                      }
                      if (!containsKey(columns, columnStdDev)) {
                        if (
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'] == undefined
                        ) {
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'] = [
                            {
                              title: 'stddevpct',
                              dataIndex: columnStdDev,
                              key: columnStdDev,
                              sorter: (a, b) => a[columnStdDev] - b[columnStdDev],
                            },
                          ];
                          iterationObject[columnStdDev] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ].stddevpct;
                        } else {
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'].push({
                            title: 'stddevpct',
                            dataIndex: columnStdDev,
                            key: columnStdDev,
                            sorter: (a, b) => a[columnStdDev] - b[columnStdDev],
                          });
                          iterationObject[columnStdDev] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ].stddevpct;
                        }
                      }
                      if (!containsKey(columns, columnSample)) {
                        if (
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'] == undefined
                        ) {
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'] = [
                            {
                              title: 'closest sample',
                              dataIndex: columnSample,
                              key: columnSample,
                              sorter: (a, b) => a[columnSample] - b[columnSample],
                              render: (text, record) => {
                                return <div>{text}</div>;
                              },
                            },
                          ];
                          iterationObject[columnSample] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ]['closest sample'];
                          iterationObject['closest_sample'] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ]['closest sample'];
                        } else {
                          columns[parentColumnIndex].children[childColumnIndex].children[
                            dataChildColumnIndex
                          ]['children'].push({
                            title: 'closest sample',
                            dataIndex: columnSample,
                            key: columnSample,
                            sorter: (a, b) => a[columnSample] - b[columnSample],
                            render: (text, record) => {
                              return <div>{text}</div>;
                            },
                          });
                          iterationObject[columnSample] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ]['closest sample'];
                          iterationObject['closest_sample'] =
                            result[iteration].iteration_data[iterationType][iterationNetwork][
                              iterationData
                            ]['closest sample'];
                        }
                      }
                    }
                  }
                } else {
                  for (var iterationData in result[iteration].iteration_data[iterationType][
                    iterationNetwork
                  ]) {
                    var columnTitle =
                      'client_hostname:' +
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].client_hostname +
                      '-server_hostname:' +
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].server_hostname +
                      '-server_port:' +
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].server_port;
                    var columnMean =
                      iterationType + '-' + iterationNetwork + '-' + columnTitle + '-' + 'mean';
                    var columnStdDev =
                      iterationType + '-' + iterationNetwork + '-' + columnTitle + '-' + 'stddevpct';
                    var columnSample =
                      iterationType +
                      '-' +
                      iterationNetwork +
                      '-' +
                      columnTitle +
                      '-' +
                      'closestsample';
                    iterationObject[columnMean] =
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].mean;
                    iterationObject[columnStdDev] =
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ].stddevpct;
                    iterationObject[columnSample] =
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ]['closest sample'];
                    iterationObject['closest_sample'] =
                      result[iteration].iteration_data[iterationType][iterationNetwork][
                        iterationData
                      ]['closest sample'];
                  }
                }
              }
            }
          }
  
          iterations.push(iterationObject);
        }
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
      configData = configCategories;
      parsedResponseData.push(responseData);
    });

    return {responseData: parsedResponseData, responseDataAll: responseDataAll, selectedRowKeys: selectedRowKeys, configData: configData, ports: ports};
}