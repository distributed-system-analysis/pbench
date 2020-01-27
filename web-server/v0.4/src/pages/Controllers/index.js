import React, { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Form, Icon, Tabs } from 'antd';

import SearchBar from '@/components/SearchBar';
import MonthSelect from '@/components/MonthSelect';
import Table from '@/components/Table';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

const { TabPane } = Tabs;

@connect(({ datastore, global, dashboard, loading, user }) => ({
  controllers: dashboard.controllers,
  indices: datastore.indices,
  selectedIndices: global.selectedIndices,
  datastoreConfig: datastore.datastoreConfig,
  favoriteControllers: user.favoriteControllers,
  loadingControllers:
    loading.effects['dashboard/fetchControllers'] ||
    loading.effects['datastore/fetchMonthIndices'] ||
    loading.effects['datastore/fetchDatastoreConfig'],
}))
class Controllers extends Component {
  constructor(props) {
    super(props);

    this.state = {
      controllers: props.controllers,
    };
  }

  componentDidMount() {
    const { controllers } = this.state;
    const { indices, selectedIndices } = this.props;

    if (controllers.length === 0 || indices.length === 0 || selectedIndices.length === 0) {
      this.queryDatastoreConfig();
    }
  }

  componentDidUpdate(prevProps) {
    const { controllers } = this.props;

    if (prevProps.controllers !== controllers) {
      this.setState({ controllers });
    }
  }

  queryDatastoreConfig = async () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'datastore/fetchDatastoreConfig',
    }).then(() => {
      this.fetchMonthIndices();
    });
  };

  fetchMonthIndices = async () => {
    const { dispatch, datastoreConfig } = this.props;

    dispatch({
      type: 'datastore/fetchMonthIndices',
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
        .map(record => {
          const match = record.controller.match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            controller: (
              <span key={record}>
                {record.controller.split(reg).map(
                  (text, index) =>
                    index > 0
                      ? [
                          // eslint-disable-next-line react/jsx-indent
                          <span key={text} style={{ color: 'orange' }}>
                            {match[0]}
                          </span>,
                          text,
                        ]
                      : text
                )}
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

  favoriteRecord = (event, value, controller) => {
    // Stop propagation from going to the next page
    event.stopPropagation();
    const { dispatch } = this.props;
    // dispatch an action to favorite controller
    dispatch({
      type: 'user/favoriteController',
      payload: controller,
    });
  };

  render() {
    const { controllers } = this.state;
    const { loadingControllers, selectedIndices, indices, favoriteControllers } = this.props;
    const columns = [
      {
        title: 'Controller',
        dataIndex: 'controller',
        key: 'controller',
        sorter: (a, b) => a.key.localeCompare(b.key),
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
      {
        title: 'Actions',
        dataIndex: 'actions',
        key: 'actions',
        render: (value, row) => {
          // if already favorited return a filled star,
          // else allow user to favorite a record
          let isFavorite = false;
          favoriteControllers.forEach(item => {
            if (item.key === row.key) {
              isFavorite = true;
            }
          });
          if (isFavorite) {
            return <Icon type="star" theme="filled" />;
          }
          return (
            <a onClick={e => this.favoriteRecord(e, null, row)}>
              <Icon type="star" />
            </a>
          );
        },
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
          <Tabs type="card">
            <TabPane tab="Controllers" key="controllers">
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
            </TabPane>
            <TabPane tab="Favorites" key="favorites">
              <Table
                style={{ marginTop: 20 }}
                columns={columns}
                dataSource={favoriteControllers}
                onRow={record => ({
                  onClick: () => {
                    this.retrieveResults(record);
                  },
                })}
                loading={loadingControllers}
              />
            </TabPane>
          </Tabs>
        </Card>
      </PageHeaderLayout>
    );
  }
}

export default Controllers;
