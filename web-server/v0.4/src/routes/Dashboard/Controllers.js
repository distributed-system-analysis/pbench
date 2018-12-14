import ReactJS, { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import moment from 'moment';
import { Card, Table, Input, Button, Icon } from 'antd';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

@connect(({ global, dashboard, loading }) => ({
  controllers: dashboard.controllers,
  startMonth: dashboard.startMonth,
  endMonth: dashboard.endMonth,
  indices: dashboard.indices,
  datastoreConfig: global.datastoreConfig,
  loadingControllers: loading.effects['dashboard/fetchControllers'],
  loadingIndices: loading.effects['dashboard/fetchMonthIndices'],
  loadingConfig: loading.effects['global/fetchDatastoreConfig']
}))
export default class Controllers extends Component {
  constructor(props) {
    super(props);

    this.state = {
      controllerSearch: [],
      searchText: '',
      filtered: false,
    };
  }

  componentDidMount() {
    this.queryDatastoreConfig();
  }

  queryDatastoreConfig = () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/fetchDatastoreConfig'
    }).then(() => {
      this.fetchMonthIndices();
    })
  };

  fetchMonthIndices = () => {
    const { dispatch, datastoreConfig } = this.props;

    dispatch({
      type: 'dashboard/fetchMonthIndices',
      payload: { datastoreConfig: datastoreConfig }
    }).then(() => {
      this.setDefaultMonth();
    });
  }

  setDefaultMonth = () => {
    const { dispatch, indices } = this.props;

    dispatch({
      type: 'dashboard/modifyControllerStartMonth',
      payload: moment(indices[0]).toString(),
    });
    dispatch({
      type: 'dashboard/modifyControllerEndMonth',
      payload: moment(indices[0]).toString(),
    });
    this.fetchControllers();
  };

  fetchControllers = () => {
    const { dispatch, datastoreConfig, startMonth, endMonth } = this.props;

    dispatch({
      type: 'dashboard/fetchControllers',
      payload: { datastoreConfig: datastoreConfig, startMonth: moment(startMonth), endMonth: moment(endMonth) },
    });
  };

  onInputChange = e => {
    this.setState({ searchText: e.target.value });
  };

  onSearch = () => {
    const { controllers } = this.props;
    const { searchText } = this.state;
    const reg = new RegExp(searchText, 'gi');
    var controllerSearch = controllers.slice();
    this.setState({
      filtered: !!searchText,
      controllerSearch: controllerSearch
        .map((record, i) => {
          const match = record.controller.match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            controller: (
              <span key={i}>
                {record.controller
                  .split(reg)
                  .map(
                    (text, i) =>
                      i > 0 ? [<span key={i} style={{ color: 'orange' }}>{match[0]}</span>, text] : text
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
          pathname: '/dashboard/results',
        })
      );
    });
  };

  emitEmpty = () => {
    this.searchInput.focus();
    this.setState({ controllerSearch: '' });
    this.setState({ searchText: '' });
  };

  render() {
    const { controllerSearch, searchText } = this.state;
    const { controllers, loadingControllers, loadingConfig, loadingIndices } = this.props;
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
          <div style={{ flexDirection: 'column' }}>
            <div>
              <Input
                style={{ width: 300, marginRight: 8 }}
                ref={ele => (this.searchInput = ele)}
                prefix={<Icon type="user" style={{ color: 'rgba(0,0,0,.25)' }} />}
                suffix={suffix}
                placeholder="Search controllers"
                value={this.state.searchText}
                onChange={this.onInputChange}
                onPressEnter={this.onSearch}
              />
              <Button type="primary" onClick={this.onSearch}>
                Search
              </Button>
            </div>
          </div>
          <Table
            style={{ marginTop: 20 }}
            columns={columns}
            dataSource={controllerSearch.length > 0 ? controllerSearch : controllers}
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
