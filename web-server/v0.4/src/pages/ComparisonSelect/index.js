import React from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Spin, notification } from 'antd';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import { filterIterations } from '../../utils/parse';

import TableFilterSelection from '@/components/TableFilterSelection';
import Button from '@/components/Button';
import Table from '@/components/Table';

@connect(({ global, dashboard, loading }) => ({
  iterations: dashboard.iterations,
  iterationParams: dashboard.iterationParams,
  results: dashboard.results,
  controllers: dashboard.controllers,
  datastoreConfig: global.datastoreConfig,
  selectedControllers: global.selectedControllers,
  selectedResults: global.selectedResults,
  selectedIterationKeys: global.selectedIterationKeys,
  loading: loading.effects['dashboard/fetchIterations'],
}))
class ComparisonSelect extends React.Component {
  constructor(props) {
    super(props);
    const { iterations, selectedIterationKeys } = props;

    this.state = {
      resultIterations: iterations,
      selectedRowKeys: selectedIterationKeys,
    };
  }

  componentDidMount() {
    const { selectedResults, datastoreConfig, dispatch } = this.props;

    dispatch({
      type: 'dashboard/fetchIterations',
      payload: { selectedResults, datastoreConfig },
    }).catch(() => {
      this.openNetworkErrorNotification('error');
    });
  }

  componentWillReceiveProps(nextProps) {
    const { iterations } = this.props;

    if (nextProps.iterations !== iterations) {
      this.setState({ resultIterations: nextProps.iterations });
      this.setState({ selectedRowKeys: nextProps.selectedIterationKeys });
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
      selectedRowKeys.forEach(rowKey => {
        selectedRowKeys[rowKey].forEach(row => {
          selectedRowData.push(resultIterations[rowKey].iterations[selectedRowKeys[rowKey][row]]);
        });
      });
      this.compareIterations(selectedRowData);
    } else {
      let selectedIterations = [];
      resultIterations.forEach(result => {
        selectedIterations = selectedIterations.concat(result.iterations);
      });
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

    const filteredIterations = filterIterations(iterations, selectedFilters);
    this.setState({ resultIterations: filteredIterations });
  };

  compareIterations = selectedIterations => {
    const { results, dispatch } = this.props;

    dispatch(
      routerRedux.push({
        pathname: '/comparison',
        state: {
          iterations: selectedIterations,
          results,
        },
      })
    );
  };

  render() {
    const { resultIterations, selectedRowKeys } = this.state;
    const { iterationParams, selectedControllers, loading } = this.props;

    return (
      <PageHeaderLayout title={selectedControllers.join(', ')}>
        <Card>
          <Spin spinning={loading} tip="Loading Iterations...">
            <Button
              type="primary"
              style={{ marginBottom: 16 }}
              name="Compare Iterations"
              onClick={this.onCompareIterations}
            />
            <TableFilterSelection onFilter={this.onFilterTable} filters={iterationParams} />
            {resultIterations.map((iteration, index) => {
              const rowSelection = {
                selectedRowKeys: selectedRowKeys[index],
                onSelect: record => this.onSelectChange(record),
              };
              return (
                <div key={iteration.resultName} style={{ marginTop: 32 }}>
                  <h2>{iteration.resultName}</h2>
                  <Table
                    rowSelection={rowSelection}
                    columns={iteration.columns}
                    dataSource={iteration.iterations}
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
