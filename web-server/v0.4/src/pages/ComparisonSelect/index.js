import React from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Spin, notification } from 'antd';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import { filterIterations } from '../../utils/parse';

import TableFilterSelection from '../../components/TableFilterSelection';
import Button from '../../components/Button';
import Table from '../../components/Table';

@connect(({ global, dashboard, loading }) => ({
  selectedControllers: dashboard.selectedControllers,
  selectedResults: dashboard.selectedResults,
  iterations: dashboard.iterations,
  results: dashboard.results,
  controllers: dashboard.controllers,
  datastoreConfig: global.datastoreConfig,
  loading: loading.effects['dashboard/fetchIterations'],
}))
class ComparisonSelect extends React.Component {
  constructor(props) {
    super(props);
    const { iterations } = props;

    this.state = {
      resultIterations: iterations.responseData,
      selectedRowKeys: iterations.selectedRowKeys,
    };
  }

  componentDidMount() {
    const { selectedResults, datastoreConfig, dispatch } = this.props;

    dispatch({
      type: 'dashboard/fetchIterations',
      payload: { selectedResults, datastoreConfig },
    }).catch(() => {
      this.openNetworkErrorNotification('error');
    })
  }

  componentWillReceiveProps(nextProps) {
    if (nextProps.iterations !== this.props.iterations) {
      this.setState({ resultIterations: nextProps.iterations.responseData });
      this.setState({ selectedRowKeys: nextProps.iterations.selectedRowKeys });
    }
  }

  openNetworkErrorNotification = type => {
    notification[type]({
      message: 'Network Error',
      description:
        "The selected iteration's resources are too large to parse in the browser. Please try another result.",
    });
  };

  onCompareIterations = () => {
    const { selectedRowKeys, resultIterations } = this.state;

    if (selectedRowKeys.flat(1).length > 0) {
      const selectedRowData = [];
      for (const item in selectedRowKeys) {
        if (selectedRowKeys[item].length > 0) {
          for (var row in selectedRowKeys[item]) {
            selectedRowData.push(resultIterations[item].iterations[selectedRowKeys[item][row]]);
          }
        }
      }
      this.compareIterations(selectedRowData);
    } else {
      let selectedIterations = [];
      resultIterations.forEach((result) => {
        selectedIterations = selectedIterations.concat(result.iterations);
      })
      this.compareIterations(selectedIterations);
    }
  };

  onSelectChange = record => {
    const { selectedRowKeys } = this.state;

    if (selectedRowKeys[record.table].includes(record.key)) {
      selectedRowKeys[record.table].splice(selectedRowKeys[record.table].indexOf(record.key), 1);
    } else {
      selectedRowKeys[record.table].push(record.key);
    }
    this.setState({ selectedRowKeys });
  };

  onFilterTable = selectedFilters => {
    const { iterations } = this.props;
    const { responseData } = iterations;

    const filteredIterations = filterIterations(responseData, selectedFilters);
    this.setState({ resultIterations: filteredIterations });
  }

  compareIterations = selectedIterations => {
    const { results, selectedResults, iterations, dispatch } = this.props;
    const { configData } = iterations;
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
          iterations: selectedIterations,
          configCategories: configCategories,
          configData: configData,
          results: results,
          selectedResults: selectedResults,
        },
      })
    );
  };

  render() {
    const { resultIterations, selectedRowKeys } = this.state;
    const { iterations, selectedControllers, loading } = this.props;
    const { configData } = iterations;

    return (
      <PageHeaderLayout title={selectedControllers.join(', ')}>
        <Card>
          <Spin spinning={loading} tip="Loading Iterations...">
            <Button
              style={{ marginBottom: 16 }}
              name="Compare Iterations"
              onClick={this.onCompareIterations}
            />
            <TableFilterSelection
              onFilter={this.onFilterTable}
              filters={configData}
            />
            {resultIterations.map((response, index) => {
              const rowSelection = {
                selectedRowKeys: selectedRowKeys[index],
                onSelect: record => this.onSelectChange(record),
              };
              return (
                <div key={response.resultName} style={{ marginTop: 32 }}>
                  <h2>{response.resultName}</h2>
                  <Table
                    rowSelection={rowSelection}
                    columns={response.columns}
                    dataSource={response.iterations}
                    bordered
                  />
                </div>
              );
            })}
          </Spin>
        </Card>
      </PageHeaderLayout>
    );
  }
}

export default connect(() => ({}))(ComparisonSelect);
