import React, { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Button, Popconfirm, Icon, Form, Modal, Input } from 'antd';

import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import Table from '@/components/Table';

const { TextArea } = Input;

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
      visible: false,
      selectedID: '',
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

    dispatch(routerRedux.push(`/share/${record.id}`));
  };

  editDescription = (id, value) => {
    const { dispatch, datastoreConfig } = this.props;
    dispatch({
      type: 'explore/editDescription',
      payload: { datastoreConfig, id, value },
    }).then(() => {
      this.fetchSharedSessions();
    });
  };

  showModal = id => {
    this.setState({
      visible: true,
      selectedID: id,
    });
  };

  handleSave = () => {
    const { selectedID } = this.state;
    const { value } = document.getElementById('editedInput');
    this.editDescription(selectedID, value);
    this.setState({
      visible: false,
    });
  };

  handleCancel = () => {
    this.setState({
      visible: false,
    });
  };

  render() {
    const { sharedSessions, visible } = this.state;
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
        colSpan: 2,
        dataIndex: 'description',
        key: 'description',
      },
      {
        title: 'Edit',
        colSpan: 0,
        dataIndex: '',
        key: 'edit',
        class: 'editDescription',
        render: record => {
          const value = <Icon type="edit" onClick={() => this.showModal(record.id)} />;
          const obj = {
            children: value,
          };
          return obj;
        },
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
        <Modal
          title="Edit the description"
          visible={visible}
          footer={[
            <Button key="back" onClick={this.handleCancel}>
              Cancel
            </Button>,
            <Button key="submit" type="primary" onClick={this.handleSave}>
              Save
            </Button>,
          ]}
        >
          <Form layout="vertical">
            <Form.Item label="Description">
              <TextArea id="editedInput" rows={2} />
            </Form.Item>
          </Form>
        </Modal>
      </PageHeaderLayout>
    );
  }
}

export default Explore;
