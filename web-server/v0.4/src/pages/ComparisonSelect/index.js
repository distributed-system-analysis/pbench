import React from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Spin, notification, Tag } from 'antd';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import { filterIterations } from '../../utils/parse';

import TableFilterSelection from '@/components/TableFilterSelection';
import Button from '@/components/Button';
import Table from '@/components/Table';

@connect(({ datastore, global, dashboard, loading }) => ({
  iterations: dashboard.iterations,
  iterationParams: dashboard.iterationParams,
  iterationPorts: dashboard.iterationPorts,
  results: dashboard.results,
  controllers: dashboard.controllers,
  datastoreConfig: datastore.datastoreConfig,
  selectedControllers: global.selectedControllers,
  selectedResults: global.selectedResults,
  selectedIterationKeys: global.selectedIterationKeys,
  loading: loading.effects['dashboard/fetchIterations'],
}))
class ComparisonSelect extends React.Component {
  constructor(props) {
    super(props);
    const { iterations } = props;

    this.state = {
      resultIterations: iterations,
      selectedRows: [],
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
    const { selectedRows, resultIterations } = this.state;

    if (selectedRows.length > 0) {
      this.compareIterations(selectedRows);
    } else {
      let selectedIterations = [];
      resultIterations.forEach(result => {
        selectedIterations = selectedIterations.concat(result.iterations);
      });
      this.compareIterations(selectedIterations);
    }
  };

  onSelectChange = selectedRows => {
    this.setState({ selectedRows });
  };

  onFilterTable = (selectedParams, selectedPorts) => {
    const { iterations } = this.props;

    const filteredIterations = filterIterations(iterations, selectedParams, selectedPorts);
    this.setState({ resultIterations: filteredIterations });
  };

  compareIterations = selectedIterations => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/updateSelectedIterations',
      payload: selectedIterations,
    }).then(() => {
      dispatch(
        routerRedux.push({
          pathname: '/comparison',
        })
      );
    });
  };

  render() {
    const { resultIterations } = this.state;
    const { iterationParams, iterationPorts, selectedControllers, loading } = this.props;
    return (
      <PageHeaderLayout
        title={selectedControllers.join(', ')}
        selectedControllers={selectedControllers}
      >
        <Card>
          <Spin spinning={loading} tip="Loading Iterations...">
            <Button
              type="primary"
              style={{ marginBottom: 16 }}
              name="Compare Iterations"
              onClick={this.onCompareIterations}
            />
            <TableFilterSelection
              onFilterTable={this.onFilterTable}
              filters={iterationParams}
              ports={iterationPorts}
            />
            {resultIterations.map(iteration => {
              const rowSelection = {
                onSelect: (record, selected, selectedRows) => this.onSelectChange(selectedRows),
                onSelectAll: (selected, selectedRows) => this.onSelectAll(selectedRows),
              };
              return (
                <div key={iteration.resultName} style={{ marginTop: 32 }}>
                  <div style={{ display: 'flex' }}>
                    <h1>{iteration.resultName}</h1>
                    <span style={{ marginLeft: 8 }}>
                      <Tag color="blue">{iteration.controllerName}</Tag>
                    </span>
                  </div>

                  <Table
                    rowSelection={rowSelection}
                    columns={iteration.columns}
                    dataSource={iteration.iterations}
                    hideDefaultSelections
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
