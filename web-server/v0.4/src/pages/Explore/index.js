import React, { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Button, Popconfirm } from 'antd';
import { getAppPath } from '../../utils/utils';

import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import Table from '@/components/Table';

@connect(({ datastore, explore, loading }) => ({
  sharedSessions: explore.sharedSessions,
  datastoreConfig: datastore.datastoreConfig,
  loadingSharedSessions: loading.effects['explore/fetchSharedSessions'],
}))
class Explore extends Component {
  constructor(props) {
    super(props);

    this.state = {
      sharedSessions: props.sharedSessions,
    };
  }

  componentDidMount() {
    this.fetchDatastoreConfig();
  }

  componentWillReceiveProps(nextProps) {
    const { sharedSessions } = this.props;

    if (nextProps.sharedSessions !== sharedSessions) {
      this.setState({ sharedSessions: nextProps.sharedSessions });
    }
  }

  fetchDatastoreConfig = () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'datastore/fetchDatastoreConfig',
    }).then(() => {
      this.fetchSharedSessions();
    });
  };

  fetchSharedSessions = () => {
    const { dispatch, datastoreConfig } = this.props;

    dispatch({
      type: 'explore/fetchSharedSessions',
      payload: { datastoreConfig },
    });
  };

  startSharedSession = record => {
    const { dispatch } = this.props;

    const parsedConfig = JSON.parse(record.config);
    window.localStorage.setItem(`persist:${getAppPath()}`, parsedConfig);

    dispatch(routerRedux.push(parsedConfig.routing.location.pathname));
  };

  render() {
    const { sharedSessions } = this.state;
    const { loadingSharedSessions } = this.props;
    const sharedSessionColumns = [
      {
        title: 'Session ID',
        dataIndex: 'id',
        key: 'id',
      },
      {
        title: 'Date Created',
        dataIndex: 'createdAt',
        key: 'createdAt',
        defaultSortOrder: 'descend',
        sorter: (a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt),
      },
      {
        title: 'Description',
        dataIndex: 'description',
        key: 'description',
      },
      {
        title: 'Action',
        dataIndex: '',
        key: 'action',
        render: (text, record) => (
          <Popconfirm
            title="Start a new dashboard session?"
            cancelText="No"
            okText="Yes"
            onConfirm={() => this.startSharedSession(record)}
          >
            <Button type="link">Start Session</Button>
          </Popconfirm>
        ),
      },
    ];

    return (
      <PageHeaderLayout title="Explore">
        <Card title="Shared Sessions" bordered={false}>
          <Table
            columns={sharedSessionColumns}
            dataSource={sharedSessions}
            loading={loadingSharedSessions}
          />
        </Card>
      </PageHeaderLayout>
    );
  }
}

export default Explore;
