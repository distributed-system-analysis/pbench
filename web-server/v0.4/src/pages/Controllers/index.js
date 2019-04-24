import React, { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Form } from 'antd';
import { compareByAlph } from '../../utils/utils';

import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import SearchBar from '@/components/SearchBar';
import MonthSelect from '@/components/MonthSelect';
import Table from '@/components/Table';

@connect(({ global, dashboard, loading }) => ({
  controllers: dashboard.controllers,
  indices: global.indices,
  selectedIndices: global.selectedIndices,
  datastoreConfig: global.datastoreConfig,
  loadingControllers:
    loading.effects['dashboard/fetchControllers'] ||
    loading.effects['global/fetchMonthIndices'] ||
    loading.effects['global/fetchDatastoreConfig'],
}))
class Controllers extends Component {
  constructor(props) {
    super(props);

    this.state = {
      controllers: props.controllers,
    };
  }

  componentDidMount() {
    const { controllers, selectedIndices, indices } = this.props;

    if (selectedIndices.length === 0 || indices.length === 0) {
      this.queryDatastoreConfig();
    } else if (controllers.length === 0) {
      this.fetchControllers();
    }
  }

  componentWillReceiveProps(nextProps) {
    const { controllers } = this.props;

    if (nextProps.controllers !== controllers) {
      this.setState({ controllers: nextProps.controllers });
    }
  }

  queryDatastoreConfig = async () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/fetchDatastoreConfig',
    }).then(() => {
      this.fetchMonthIndices();
    });
  };

  fetchMonthIndices = async () => {
    const { dispatch, datastoreConfig } = this.props;

    dispatch({
      type: 'global/fetchMonthIndices',
      payload: { datastoreConfig },
    }).then(() => {
      this.fetchControllers();
    });
  };

  fetchControllers = () => {
    const { dispatch, datastoreConfig, selectedIndices } = this.props;

    dispatch({
      type: 'dashboard/fetchControllers',
      payload: { datastoreConfig, selectedIndices },
    });
  };

  updateSelectedIndices = value => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/updateSelectedIndices',
      payload: value,
    });
  };

  onSearch = searchValue => {
    const { controllers } = this.props;
    const reg = new RegExp(searchValue, 'gi');
    const controllersSearch = controllers.slice();
    this.setState({
      controllers: controllersSearch
        .map((record) => {
          const match = record.controller.match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            controller: (
              <span key={record}>
                {record.controller.split(reg).map((text, index) => (
                  index > 0
                    ? [
                      <span key={text} style={{ color: 'orange' }}>
                        {match[0]}
                      </span>,
                        text,
                      ]
                    : text
                ))}
              </span>
            ),
          };
        })
        .filter(record => !!record),
    });
  };

  retrieveResults = controller => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/updateSelectedControllers',
      payload: [controller.key],
    }).then(() => {
      dispatch(
        routerRedux.push({
          pathname: '/results',
        })
      );
    });
  };

  render() {
    const { controllers } = this.state;
    const { loadingControllers, selectedIndices, indices } = this.props;
    const columns = [
      {
        title: 'Controller',
        dataIndex: 'controller',
        key: 'controller',
        sorter: (a, b) => compareByAlph(a['run.controller'], b['run.controller']),
      },
      {
        title: 'Last Modified',
        dataIndex: 'last_modified_string',
        key: 'last_modified_string',
        sorter: (a, b) => a.last_modified_value - b.last_modified_value,
      },
      {
        title: 'Results',
        dataIndex: 'results',
        key: 'results',
        sorter: (a, b) => a.results - b.results,
      },
    ];

    return (
      <PageHeaderLayout title="Controllers">
        <Card bordered={false}>
          <Form layout="inline" style={{ display: 'flex', flex: 1, alignItems: 'center' }}>
            <SearchBar
              style={{ marginRight: 32 }}
              placeholder="Search controllers"
              onSearch={this.onSearch}
            />
            <MonthSelect
              indices={indices}
              reFetch={this.fetchControllers}
              onChange={this.updateSelectedIndices}
              value={selectedIndices}
            />
          </Form>
          <Table
            style={{ marginTop: 20 }}
            columns={columns}
            dataSource={controllers}
            onRow={record => ({
              onClick: () => {
                this.retrieveResults(record);
              },
            })}
            loading={loadingControllers}
          />
        </Card>
      </PageHeaderLayout>
    );
  }
}

export default Controllers;
