import { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Table, Input, Button, Icon, Form, Select, notification } from 'antd';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
const FormItem = Form.Item;

@connect(({ global, dashboard, loading }) => ({
  controllers: dashboard.controllers,
  indices: global.indices,
  selectedIndices: global.selectedIndices,
  selectorIndices: global.selectorIndices,
  datastoreConfig: global.datastoreConfig,
  loadingControllers: loading.effects['dashboard/fetchControllers'],
  loadingIndices: loading.effects['global/fetchMonthIndices'],
  loadingConfig: loading.effects['global/fetchDatastoreConfig'],
}))
export default class Controllers extends Component {
  constructor(props) {
    super(props);

    this.state = {
      controllers: [],
      selectedIndicesUpdated: false,
      searchText: ''
    };
  }

  componentDidMount() {
    this.queryDatastoreConfig();
  }

  componentDidUpdate(prevProps) {
    const { controllers } = this.props;
    const prevControllers = prevProps.controllers;

    if (controllers !== prevControllers) {
      this.setState({ controllers });
    }
  }

  queryDatastoreConfig = () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/fetchDatastoreConfig',
    }).then(() => {
      this.fetchMonthIndices();
    }).catch((err) => {
      console.log(err)
    });
  };

  fetchMonthIndices = async () => {
    const { dispatch, datastoreConfig } = this.props;

    dispatch({
      type: 'global/fetchMonthIndices',
      payload: { datastoreConfig: datastoreConfig },
    }).then(() => {
      Promise.resolve(this.updateSelectedIndices(['0'])).then(() => {
        this.fetchControllers();
      });
    });
  };

  fetchControllers = () => {
    const { dispatch, datastoreConfig, selectedIndices } = this.props;

    dispatch({
      type: 'dashboard/fetchControllers',
      payload: { datastoreConfig: datastoreConfig, selectedIndices: selectedIndices },
    });
  };

  openErrorNotification = month => {
    notification.error({
      message: 'Index Unavailable',
      description: month + ' does not contain any documents. Please select a different month.',
    });
  };

  updateSelectedIndices = value => {
    const { dispatch, indices } = this.props;
    let selectedIndices = [];

    value.map(item => {
      selectedIndices.push(indices[item]);
    });

    dispatch({
      type: 'global/updateSelectedIndices',
      payload: selectedIndices,
    }).then(() => {
      dispatch({
        type: 'global/updateSelectorIndices',
        payload: value,
      });
    });
  };

  onInputChange = e => {
    this.setState({ searchText: e.target.value });
  };

  onSearch = () => {
    const { searchText } = this.state;
    const { controllers } = this.props;
    const reg = new RegExp(searchText, 'gi');
    const controllersSearch = controllers.slice();
    this.setState({
      controllers: controllersSearch
        .map((record, i) => {
          const match = record.controller.match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            controller: (
              <span key={i}>
                {record.controller.split(reg).map(
                  (text, i) =>
                    i > 0
                      ? [
                          <span key={i} style={{ color: 'orange' }}>
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

  retrieveResults = params => {
    const { dispatch } = this.props;

    dispatch({
      type: 'dashboard/updateSelectedController',
      payload: params.key,
    }).then(() => {
      dispatch(
        routerRedux.push({
          pathname: '/results',
        })
      );
    });
  };

  emitEmpty = () => {
    this.searchInput.focus();
    this.setState({ controllers: this.props.controllers });
    this.setState({ searchText: '' });
  };

  render() {
    const { controllers, searchText, selectedIndicesUpdated } = this.state;
    const {
      loadingControllers,
      loadingConfig,
      loadingIndices,
      selectorIndices,
      indices,
    } = this.props;
    const suffix = searchText ? <Icon type="close-circle" onClick={this.emitEmpty} /> : null;
    const columns = [
      {
        title: 'Controller',
        dataIndex: 'controller',
        key: 'controller',
        sorter: (a, b) => compareByAlph(a.controller, b.controller),
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
          <Form layout={'inline'} style={{ display: 'flex', flex: 1, alignItems: 'center' }}>
            <FormItem>
              <Input
                style={{ width: 300 }}
                ref={ele => (this.searchInput = ele)}
                prefix={<Icon type="search" style={{ color: 'rgba(0,0,0,.25)' }} />}
                suffix={suffix}
                placeholder="Search controllers"
                value={this.state.searchText}
                onChange={this.onInputChange}
                onPressEnter={this.onSearch}
              />
            </FormItem>
            <FormItem>
              <Button type="primary" onClick={this.onSearch}>
                {'Search'}
              </Button>
            </FormItem>
            <FormItem
              label="Selected Months"
              colon={false}
              style={{ marginLeft: 16, fontWeight: '500' }}
            >
              <Select
                mode="multiple"
                style={{ width: '100%' }}
                placeholder="Select index"
                value={selectorIndices}
                onChange={value => {
                  this.updateSelectedIndices(value);
                  this.setState({ selectedIndicesUpdated: true });
                }}
                tokenSeparators={[',']}
              >
                {indices.map((index, i) => {
                  return <Select.Option key={i}>{index}</Select.Option>;
                })}
              </Select>
            </FormItem>
            <FormItem>
              <Button
                type="primary"
                disabled={selectedIndicesUpdated ? false : true}
                onClick={() => {
                  this.fetchControllers();
                  this.setState({ selectedIndicesUpdated: false });
                }}
              >
                {'Update'}
              </Button>
            </FormItem>
          </Form>
          <Table
            style={{ marginTop: 20 }}
            columns={columns}
            dataSource={controllers}
            defaultPageSize={20}
            onRowClick={this.retrieveResults.bind(this)}
            loading={loadingControllers || loadingConfig || loadingIndices}
            showSizeChanger={true}
            showTotal={true}
            pagination={{ pageSize: 20 }}
            bordered
          />
        </Card>
      </PageHeaderLayout>
    );
  }
}

function compareByAlph(a, b) {
  if (a > b) {
    return -1;
  }
  if (a < b) {
    return 1;
  }
  return 0;
}
