import ReactJS from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Select, Card, Spin, Tag, Table, Button, notification } from 'antd';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import cloneDeep from 'lodash/cloneDeep';
import { parseIterationData } from '../../utils/parse';

import { queryIterations } from '../../services/dashboard';

@connect(({ global, dashboard, loading }) => ({
  selectedController: dashboard.selectedController,
  selectedResults: dashboard.selectedResults,
  iterations: dashboard.iterations,
  results: dashboard.results,
  controllers: dashboard.controllers,
  datastoreConfig: global.datastoreConfig,
  loading: loading.effects['dashboard/fetchIterations'],
}))
class ComparisonSelect extends ReactJS.Component {
  constructor(props) {
    super(props);

    this.state = {
      responseData: [],
      responseDataAll: [],
      loading: true,
      loadingButton: false,
      tables: [],
      selectedRowKeys: [],
      rowSelections: [],
      selectedPort: 'all',
      ports: [],
      configData: [],
      selectedConfig: [],
    };
  }

  componentDidMount() {
    this.setState({ loading: true });
    const { selectedResults, datastoreConfig } = this.props;

    queryIterations({ selectedResults: selectedResults, datastoreConfig: datastoreConfig })
      .then(res => {
        let parsedIterationData = parseIterationData(res);
        this.setState({
          responseData: parsedIterationData.responseData,
          selectedRowKeys: parsedIterationData.selectedRowKeys,
          responseDataAll: parsedIterationData.responseDataAll,
          configData: parsedIterationData.configData,
          ports: parsedIterationData.ports,
          loading: false,
        });
      })
      .catch(err => {
        this.openNetworkErrorNotification('error');
        this.setState({ loading: false });
      });
  }

  openNetworkErrorNotification = type => {
    notification[type]({
      message: 'Network Error',
      description:
        "The selected iteration's resources are too large to parse in the browser. Please try another result.",
    });
  };

  openNotificationWithIcon = type => {
    notification[type]({
      message: 'Please select two results for comparison.',
    });
  };

  onCompareIterations = () => {
    const { selectedRowKeys, responseData } = this.state;
    if (selectedRowKeys.length < 2) {
      this.openNotificationWithIcon('error');
    }
    var selectedRowData = [];
    for (var item in selectedRowKeys) {
      if (selectedRowKeys[item].length > 0) {
        for (var row in selectedRowKeys[item]) {
          selectedRowData.push(responseData[item].iterations[selectedRowKeys[item][row]]);
        }
      }
    }
    this.compareIterations(selectedRowData);
  };

  onSelectChange = record => {
    var { selectedRowKeys } = this.state;
    if (selectedRowKeys[record.table].includes(record.key)) {
      selectedRowKeys[record.table].splice(selectedRowKeys[record.table].indexOf(record.key), 1);
    } else {
      selectedRowKeys[record.table].push(record.key);
    }
    this.setState({ selectedRowKeys });
  };

  compareIterations = params => {
    const { configData } = this.state;
    const { results, selectedController, selectedResults } = this.props;
    const { dispatch } = this.props;
    const configCategories = Object.keys(configData);

    dispatch({
      type: 'dashboard/modifyConfigCategories',
      payload: configCategories,
    });
    dispatch({
      type: 'dashboard/modifyConfigData',
      payload: configData,
    });
    dispatch({
      type: 'dashboard/modifySelectedResults',
      payload: selectedResults,
    });

    dispatch(
      routerRedux.push({
        pathname: '/comparison',
        state: {
          iterations: params,
          configCategories: configCategories,
          configData: configData,
          results: results,
          controller: selectedController,
          selectedResults: selectedResults,
        },
      })
    );
  };

  compareAllIterations = () => {
    const { responseDataAll, configData } = this.state;
    const { results, selectedController, selectedResults } = this.props;
    const { dispatch } = this.props;
    const configCategories = Object.keys(configData);

    dispatch({
      type: 'dashboard/modifyConfigCategories',
      payload: configCategories,
    });
    dispatch({
      type: 'dashboard/modifyConfigData',
      payload: configData,
    });
    dispatch({
      type: 'dashboard/modifySelectedResults',
      payload: selectedResults,
    });

    dispatch(
      routerRedux.push({
        pathname: '/comparison',
        state: {
          iterations: responseDataAll,
          configCategories: configCategories,
          configData: configData,
          results: results,
          controller: selectedController,
          selectedResults: selectedResults,
        },
      })
    );
  };

  configChange = (value, category) => {
    var { selectedConfig } = this.state;
    if (value == undefined) {
      delete selectedConfig[category];
    } else {
      selectedConfig[category] = value;
    }
    this.setState({ selectedConfig: selectedConfig });
  };

  clearFilters = () => {
    this.setState({
      selectedConfig: [],
      selectedPort: 'all',
    });
  };

  portChange = value => {
    this.setState({ selectedPort: value });
  };

  render() {
    const {
      responseData,
      loading,
      loadingButton,
      selectedRowKeys,
      selectedPort,
      ports,
      configData,
      selectedConfig,
    } = this.state;
    const { selectedController } = this.props;

    var selectedRowNames = [];
    for (var item in selectedRowKeys) {
      if (selectedRowKeys[item].length > 0) {
        for (var row in selectedRowKeys[item]) {
          selectedRowNames.push(
            responseData[item].iterations[selectedRowKeys[item][row]].iteration_name
          );
        }
      }
    }

    var responseDataCopy = [];
    for (var response in responseData) {
      responseDataCopy[response] = [];
      responseDataCopy[response]['columns'] = cloneDeep(responseData[response].columns);
      responseDataCopy[response]['iterations'] = cloneDeep(responseData[response].iterations);
      responseDataCopy[response]['resultName'] = cloneDeep(responseData[response].resultName);
    }

    for (var response in responseDataCopy) {
      var responseColumns = responseDataCopy[response].columns;
      var responseIterations = responseDataCopy[response].iterations;
      for (var column in responseColumns) {
        if (responseColumns[column]['children'] != undefined) {
          for (var networkColumn in responseColumns[column]['children']) {
            if (responseColumns[column]['children'][networkColumn]['children'] != undefined) {
              for (var portColumn in responseColumns[column]['children'][networkColumn][
                'children'
              ]) {
                if (
                  !responseColumns[column]['children'][networkColumn]['children'][portColumn][
                    'title'
                  ].includes(selectedPort)
                ) {
                  responseColumns[column]['children'][networkColumn]['children'].splice(
                    portColumn,
                    1
                  );
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
          var found = [];
          for (var config in selectedConfig) {
            if (
              (selectedConfig[config] !== undefined) &
              (selectedConfig[config] == responseIterations[iteration][config])
            ) {
              found.push(true);
            }
          }
          if (found.length == selectedConfigLength) {
            filteredResponseData.push(responseIterations[iteration]);
          }
        }
        responseDataCopy[response].iterations = filteredResponseData;
      }
    }

    return (
      <PageHeaderLayout title={selectedController}>
        <Spin style={{ marginTop: 200, alignSelf: 'center' }} spinning={loading}>
          <Card style={{ marginBottom: 16 }}>
            <Card
              type="inner"
              title={<h3 style={{ marginTop: 8 }}>{'Selected Iterations'}</h3>}
              extra={
                <div>
                  <Button
                    type="primary"
                    style={{ marginRight: 8 }}
                    onClick={this.compareAllIterations}
                    loading={loadingButton}
                  >
                    {'Compare All Iterations'}
                  </Button>
                  <Button
                    type="primary"
                    onClick={this.onCompareIterations}
                    disabled={selectedRowNames.length == 0}
                    loading={loadingButton}
                  >
                    {'Compare Selected Iterations'}
                  </Button>
                </div>
              }
            >
              {selectedRowNames.length > 0 ? (
                <div>
                  {selectedRowNames.map((row, i) => (
                    <Tag style={{ fontSize: 16 }} key={i} id={i}>
                      {row}
                    </Tag>
                  ))}
                </div>
              ) : (
                <Card.Meta description="Start by comparing all iterations or selecting specific iterations from the result tables below." />
              )}
            </Card>
            <Card
              type="inner"
              title={<h3 style={{ marginTop: 8 }}>{'Iteration Filters'}</h3>}
              style={{ marginTop: 16 }}
              extra={
                <Button
                  style={{ marginLeft: 8 }}
                  type="primary"
                  onClick={this.clearFilters}
                  loading={loadingButton}
                >
                  {'Clear Filters'}
                </Button>
              }
            >
              {/*<Select
                  allowClear={true}
                  placeholder={'Filter Hostname & Port'}
                  style={{ marginTop: 16, width: 160 }}
                  onChange={this.portChange}
                  value={selectedPort}
                >
                  {ports.map((port, i) => (
                    <Select.Option value={port}>{port}</Select.Option>
                  ))}
                  </Select>*/}
              {Object.keys(configData).map((category, i) => (
                <Select
                  key={i}
                  allowClear={true}
                  placeholder={category}
                  style={{ marginLeft: 8, width: 160 }}
                  value={selectedConfig[category]}
                  onChange={value => this.configChange(value, category)}
                >
                  {configData[category].map((categoryData, i) => (
                    <Select.Option key={i} value={categoryData}>
                      {categoryData}
                    </Select.Option>
                  ))}
                </Select>
              ))}
            </Card>
          </Card>
          {responseDataCopy.map((response, i) => {
            const rowSelection = {
              selectedRowKeys: selectedRowKeys[i],
              onSelect: record => this.onSelectChange(record),
              hideDefaultSelections: true,
              fixed: true,
            };
            return (
              <Card key={i} style={{ marginBottom: 16 }}>
                <h2>{response.resultName}</h2>
                <Table
                  key={i}
                  style={{ marginTop: 16 }}
                  rowSelection={rowSelection}
                  columns={response.columns}
                  dataSource={response.iterations}
                  pagination={{ pageSize: 20 }}
                  bordered
                />
              </Card>
            );
          })}
        </Spin>
      </PageHeaderLayout>
    );
  }
}

export default connect(() => ({}))(ComparisonSelect);
