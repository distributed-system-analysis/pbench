import React, { PropTypes } from 'react';
import {Divider, Affix, Select, Card, Menu, Dropdown, Collapse, Spin, Tag, Table, Input, Button, LocaleProvider} from 'antd';
import { Layout as TableLayout } from 'antd';
import history from '../../core/history';
import Layout from '../../components/Layout';
import constants from '../../core/constants';
import axios, { CancelToken } from 'axios';
import cloneDeep from 'lodash/cloneDeep';
const Panel = Collapse.Panel;

class CompareResults extends React.Component {
  static propTypes = {
    results: React.PropTypes.array
  };

  constructor(props) {
    super(props);

    this.state = {
      responseData: [],
      responseDataAll: [],
      loading: true,
      loadingButton: false,
      selectedRowKeys: [],
      rowSelections: [],
      selectedPort: "all",
      ports: [],
      configData: [],
      selectedConfig: []
    };
  }

  componentDidMount() {
    this.setState({loading: true});
    const { results } = this.props;
    var iterationRequests = [];
    for (var result in results) {
      iterationRequests.push(axios.get('http://pbench.perf.lab.eng.bos.redhat.com/results/' + encodeURI((results[result].controller).slice(0, (results[result].controller).indexOf("."))) +'/'+ encodeURI(results[result].result) + '/result.json'))
    }
    axios.all(iterationRequests)
    .then(args => {
      var responseData = [];
      var rowSelections = [];
      var selectedRowKeys = this.state.selectedRowKeys;
      for (var response in args) {
        if (args[response].data != null) {
          var iterationData = args[response].data;
          var controllerName = args[response].config.url.split('/')[4]
          var resultName = args[response].config.url.split('/')[5]
          responseData.push(this.parseJSONData(iterationData, resultName, controllerName));
          selectedRowKeys.push([])
          this.setState({selectedRowKeys: selectedRowKeys})
          var tableSelections = selectedRowKeys[response];
          rowSelections.push({
            selectedRowKeys: tableSelections,
            onChange: (selectedRowKeys, selectedRows) => {
              this.onSelectChange(selectedRowKeys, selectedRows, response);
            },
            hideDefaultSelections: true,
            fixed: true,
            table: response
          })
        }
      }
      this.setState({rowSelections: rowSelections});
      this.setState({responseData: responseData});
      this.setState({loading: false});
    });
  }

  start = () => {
    this.setState({ loadingButton: true });
    setTimeout(() => {
      this.setState({
        selectedRowKeys: [],
        loadingButton: false,
      });
    }, 1000);
  }

  openNotificationWithIcon = (type) => {
    notification[type]({
      message: 'Please select two results for comparison.',
      placement: 'bottomRight'
    });
  }

  onCompareIterations = () => {
    const { selectedRowKeys, responseData } = this.state;
    if (selectedRowKeys.length < 2) {
      this.openNotificationWithIcon('error')
    }
    var selectedRowData = [];
    for (var item in selectedRowKeys) {
      if (selectedRowKeys[item].length > 0) {
        for (var row in selectedRowKeys[item]) {
          selectedRowData.push(responseData[item].iterations[selectedRowKeys[item][row]]);
        }
      }
    }
    this.compareIterations(selectedRowData)
  }

  updateSelection = (table) => {
    this.setState({tableSelected: table})
  }

  onSelectChange = (selectedKey, selectedRow, selectedTable) => {
    var { selectedRowKeys } = this.state;
    selectedRowKeys[selectedTable].push(parseInt(selectedKey[selectedKey.length - 1]))
    this.setState({ selectedRowKeys });
  }

  parseJSONData(response, resultName, controllerName) {
    var responseData = [];
    var columns = [{
      title: 'Iteration Number',
      dataIndex: 'iteration_number',
      fixed: 'left',
      width: 115,
      key: 'iteration_number',
      sorter: (a, b) => a.iteration_number - b.iteration_number
    }, {
      title: 'Iteration Name',
      dataIndex: 'iteration_name',
      fixed: 'left',
      width: 150,
      key: 'iteration_name'
    }];
    var iterations = [];
    var ports = [];
    var configCategories = {};

    for (var iteration in response) {
      var iterationObject = {key: iteration, iteration_name: response[iteration].iteration_name, iteration_number: response[iteration].iteration_number, result_name: resultName, controller_name: controllerName};
      var configObject = {};
      var keys = [];
      if (response[iteration].iteration_data.parameters.benchmark[0] != undefined ) {
        var keys = Object.keys(response[iteration].iteration_data.parameters.benchmark[0])
        for (var key in keys) {
          if (keys[key] != "uid" & keys[key] != "clients" & keys[key] != "servers" & keys[key] != "max_stddevpct") {
            if (!Object.keys(configCategories).includes(keys[key])) {
              var obj = {};
              configCategories[keys[key]] = [response[iteration].iteration_data.parameters.benchmark[0][keys[key]]]
            } else {
              if (!configCategories[keys[key]].includes(response[iteration].iteration_data.parameters.benchmark[0][keys[key]])) {
                configCategories[keys[key]].push(response[iteration].iteration_data.parameters.benchmark[0][keys[key]])
              }
            }
            configObject[keys[key]] = response[iteration].iteration_data.parameters.benchmark[0][keys[key]]
          }
        }
      }
      var iterationObject = Object.assign({}, iterationObject, configObject)
      for (var iterationType in response[iteration].iteration_data) {
        if (iterationType != "parameters") {
          if (!this.containsTitle(columns, iterationType)) {
            columns.push({title: iterationType});
          }
          for (var iterationNetwork in (response[iteration].iteration_data[iterationType])) {
            var parentColumnIndex = this.getColumnIndex(columns, iterationType);
            if (!this.containsIteration(columns[parentColumnIndex], iterationNetwork)) {
              if (columns[parentColumnIndex]["children"] == undefined) {
                columns[parentColumnIndex]["children"] = [{title: iterationNetwork}];
              } else {
                columns[parentColumnIndex]["children"].push({title: iterationNetwork});
              }
              for (var iterationData in (response[iteration].iteration_data[iterationType][iterationNetwork])) {
                var columnTitle = "client_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].client_hostname + "-server_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_hostname + "-server_port:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_port;
                if (columns[parentColumnIndex]["children"] == undefined) {
                  var childColumnIndex = 0;
                } else {
                  var childColumnIndex = this.getColumnIndex(columns[parentColumnIndex].children, iterationNetwork);
                }
                if (!this.containsIteration(columns[parentColumnIndex].children[childColumnIndex], columnTitle)) {
                  if (columns[parentColumnIndex].children[childColumnIndex]["children"] == undefined) {
                    columns[parentColumnIndex].children[childColumnIndex]["children"] = [{title: columnTitle, dataIndex: columnTitle}];
                  } else {
                    columns[parentColumnIndex].children[childColumnIndex]["children"].push({title: columnTitle});
                  }
                  var columnValue = columnTitle.split(":")[3];
                  if (!ports.includes(columnValue)) {
                    ports.push(columnValue)
                  }
                  var columnMean = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "mean";
                  var columnStdDev = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "stddevpct";
                  var columnSample = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "closestsample";
                  var dataChildColumnIndex = this.getColumnIndex(columns[parentColumnIndex].children[childColumnIndex]["children"], columnTitle);
                  if (dataChildColumnIndex == undefined) {
                    dataChildColumnIndex = 0;
                  }
                  if (!this.containsKey(columns, columnMean)) {
                    if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "mean", dataIndex: columnMean, key: columnMean, sorter: (a, b) => a[columnMean] - b[columnMean]}];
                        iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].mean;
                    } else {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "mean", dataIndex: columnMean, key: columnMean, sorter: (a, b) => a[columnMean] - b[columnMean]});
                        iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].mean;
                    }
                  }
                  if (!this.containsKey(columns, columnStdDev)) {
                    if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "stddevpct", dataIndex: columnStdDev, key: columnStdDev, sorter: (a, b) => a[columnStdDev] - b[columnStdDev]}];
                        iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].stddevpct;
                    } else {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "stddevpct", dataIndex: columnStdDev, key: columnStdDev, sorter: (a, b) => a[columnStdDev] - b[columnStdDev]});
                        iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].stddevpct;
                    }
                  }
                  if (!this.containsKey(columns, columnSample)) {
                    if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "closest sample", dataIndex: columnSample, key: columnSample, sorter: (a, b) => a[columnSample] - b[columnSample], render: (text, record) => {
                            return (
                              <div>{text}</div>
                            );
                          },
                        }];
                        iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                        iterationObject['closest_sample'] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                    } else {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "closest sample", dataIndex: columnSample, key: columnSample, sorter: (a, b) => a[columnSample] - b[columnSample], render: (text, record) => {
                            return (
                              <div>{text}</div>
                            );
                          },
                        });
                        iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                        iterationObject['closest_sample'] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                    }
                  }
                }
              }
            } else {
              for (var iterationData in (response[iteration].iteration_data[iterationType][iterationNetwork])) {
                var columnTitle = "client_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].client_hostname + "-server_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_hostname + "-server_port:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_port;
                var columnMean = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "mean";
                var columnStdDev = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "stddevpct";
                var columnSample = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "closestsample";
                iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].mean;
                iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].stddevpct;
                iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                iterationObject['closest_sample'] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
              }
            }
          }
        }
      }
      iterations.push(iterationObject);
    };
    responseData["resultName"] = resultName;
    responseData["columns"] = columns;
    responseData["iterations"] = iterations;
    this.setState({configData: configCategories});
    this.setState({responseDataAll: this.state.responseDataAll.concat(iterations)});
    return responseData;
  }

  containsKey(columns, item) {
    var contains = false;
    for (var column in columns) {
      if (columns[column].key == item) {
        return true;
      }
      var keys = Object.keys(columns[column]);
      for (var key in keys) {
        if (keys[key] == "children") {
          this.containsKey(columns[column].children, item);
        }
      }
    }
    return contains;
  }

  containsTitle(columns, item) {
    var contains = false;
    for (var column in columns) {
      if (columns[column].title == item) {
        return true;
      }
      var keys = Object.keys(columns[column]);
      for (var key in keys) {
        if (keys[key] == "children") {
          this.containsTitle(columns[column].children, item);
        }
      }
    }
    return contains;
  }

  containsIteration(columns, item) {
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

  getColumnIndex(columns, item) {
    for (var column in columns) {
      if (columns[column].title == item) {
          return column;
      }
    }
  }

  compareIterations = (params) => {
    var { configData } = this.state;
    var configCategories = Object.keys(configData);
    history.push({
      pathname: '/dashboard/results/comparison/iterations',
      state: {
        iterations: params,
        configCategories: configCategories
      }
    })
  }

  compareAllIterations = () => {
    var { responseDataAll, configData } = this.state;
    var configCategories = Object.keys(configData);
    history.push({
      pathname: '/dashboard/results/comparison/iterations',
      state: {
        iterations: responseDataAll,
        configCategories: configCategories
      }
    })
  }

  configChange = (value, category) => {
    var { selectedConfig } = this.state;
    if (value == undefined) {
      delete selectedConfig[category];
    } else {
      selectedConfig[category] = value;
    }
    this.setState({selectedConfig: selectedConfig})
  }

  clearFilters = () => {
    this.setState({selectedConfig: []})
  }

  portChange = (value) => {
    this.setState({selectedPort: value})
  }

  render() {
    const { responseData, loading, loadingButton, selectedRowKeys, rowSelections, selectedPort, ports, configData, selectedConfig } = this.state;
    var selectedRowNames = [];
    for (var item in selectedRowKeys) {
      if (selectedRowKeys[item].length > 0) {
        for (var row in selectedRowKeys[item]) {
          selectedRowNames.push(responseData[item].iterations[selectedRowKeys[item][row]].iteration_name);
        }
      }
    }

    var responseDataCopy = [];
    for (var response in responseData) {
      responseDataCopy[response] = [];
      responseDataCopy[response]["columns"] = cloneDeep(responseData[response].columns)
      responseDataCopy[response]["iterations"] = cloneDeep(responseData[response].iterations)
      responseDataCopy[response]["resultName"] = cloneDeep(responseData[response].resultName)
    }

    for (var response in responseDataCopy) {
      var responseColumns = responseDataCopy[response].columns;
      var responseIterations = responseDataCopy[response].iterations;
      for (var column in responseColumns) {
        if (responseColumns[column]["children"] != undefined) {
          for (var networkColumn in responseColumns[column]["children"]) {
            if (responseColumns[column]["children"][networkColumn]["children"] != undefined) {
              for (var portColumn in responseColumns[column]["children"][networkColumn]["children"]) {
                if (!responseColumns[column]["children"][networkColumn]["children"][portColumn]["title"].includes(selectedPort)) {
                  responseColumns[column]["children"][networkColumn]["children"].splice(portColumn, 1);
                }
              }
            }
          }
        }
      }
      var selectedConfigLength = Object.keys(selectedConfig).length;
      if (selectedConfigLength > 0) {
        var filteredResponseData = [];
        for (var iteration in responseIterations) {
          var iterationKeys = Object.keys(responseIterations[iteration])
          var found = [];
          for (var config in selectedConfig) {
            if (selectedConfig[config] !== undefined & selectedConfig[config] == responseIterations[iteration][config]) {
              found.push(true)
            }
          }
          if (found.length == selectedConfigLength) {
            filteredResponseData.push(responseIterations[iteration])
          }
        }
        responseDataCopy[response].iterations = filteredResponseData;
      }
    }

    return (
      <div style={{ marginLeft: 80 }} className="container-fluid" ref={(node) => { this.container = node; }}>
        <Spin style={{marginTop: 200, alignSelf: 'center'}} spinning={loading}>
          {selectedRowNames.length > 0 ?
              <Card style={{marginTop: 16}} title={<Button type="primary" onClick={this.onCompareIterations} disabled={selectedRowNames.length == 0} loading={loadingButton}>Compare Iterations</Button>} type="inner">
                {selectedRowNames.map((row,i) =>
                  <Tag id={i}>{row}</Tag>
                )}
              </Card>
            :
            <div></div>
          }
          <Button type="primary" style={{alignSelf: 'flex-start', marginTop: 32}} onClick={this.compareAllIterations} loading={loadingButton}>Compare All Iterations</Button>
          <Button style={{marginLeft: 8}} onClick={this.clearFilters} loading={loadingButton}>Clear Filters</Button>
          <br></br>
          <Select allowClear={true} placeholder="Filter Hostname & Port" style={{ marginTop: 16, width: 160 }} onChange={this.portChange}>
            {ports.map((port, i) =>
              <Select.Option value={port}>{port}</Select.Option>
            )}
          </Select>
          {Object.keys(configData).map((category, i) =>
            <Select allowClear={true} placeholder={category} style={{ marginLeft: 8, width: 160 }} onChange={(value) => this.configChange(value, category)}>
              {configData[category].map((categoryData, i) =>
                <Select.Option value={categoryData}>{categoryData}</Select.Option>
              )}
            </Select>
          )}
          {responseDataCopy.map((response, i) =>
              <div>
                <h2>{response.resultName}</h2>
                <Table key={i} style={{marginTop: 20}} rowSelection={rowSelections[i]} columns={response.columns} dataSource={response.iterations} bordered/>
              </div>
          )}
        </Spin>
      </div>
    );
  }

}

export default CompareResults;
