import { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Tag, Card, Table, Input, Button } from 'antd';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

@connect(({ global, dashboard, loading }) => ({
  selectedIndices: global.selectedIndices,
  results: dashboard.results,
  selectedController: dashboard.selectedController,
  datastoreConfig: global.datastoreConfig,
  loading: loading.effects['dashboard/fetchResults'],
}))
export default class Results extends Component {
  constructor(props) {
    super(props);

    this.state = {
      resultSearch: [],
      selectedRowKeys: [],
      selectedRowNames: [],
      loading: false,
      loadingButton: false,
      searchText: '',
      filtered: false,
    };
  }

  componentDidMount() {
    const { dispatch, datastoreConfig, selectedIndices, selectedController } = this.props;

    dispatch({
      type: 'dashboard/fetchResults',
      payload: {
        datastoreConfig: datastoreConfig,
        selectedIndices: selectedIndices,
        controller: selectedController,
      },
    });
  }

  openNotificationWithIcon = type => {
    notification[type]({
      message: 'Please select two results for comparison.',
      placement: 'bottomRight',
    });
  };

  onCompareResults = () => {
    const { selectedRowKeys } = this.state;
    const { selectedController, results } = this.props;
    var selectedResults = [];
    for (var item in selectedRowKeys) {
      var result = results[selectedRowKeys[item]];
      result['controller'] = selectedController;
      selectedResults.push(results[selectedRowKeys[item]]);
    }
    this.compareResults(selectedResults);
  };

  onSelectChange = selectedRowKeys => {
    const { dispatch, results } = this.props;
    let selectedRowNames = [];
    selectedRowKeys.map(row => {
      selectedRowNames.push(results[row]);
    });
    this.setState({ selectedRowKeys });

    dispatch({
      type: 'dashboard/updateSelectedResults',
      payload: selectedRowNames,
    });
  };

  onInputChange = e => {
    this.setState({ searchText: e.target.value });
  };

  onSearch = () => {
    const { searchText } = this.state;
    const { results } = this.props;
    const reg = new RegExp(searchText, 'gi');
    var resultSearch = results.slice();
    this.setState({
      filtered: !!searchText,
      resultSearch: resultSearch
        .map((record, i) => {
          const match = record.result.match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            result: (
              <span key={i}>
                {record['run.name'].split(reg).map(
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

  compareResults = () => {
    const { dispatch } = this.props;

    dispatch(
      routerRedux.push({
        pathname: '/dashboard/comparison-select',
      })
    );
  };

  retrieveResults = params => {
    const { dispatch } = this.props;

    dispatch({
      type: 'dashboard/updateSelectedResults',
      payload: params,
    });

    dispatch(
      routerRedux.push({
        pathname: '/dashboard/summary',
      })
    );
  };

  render() {
    const { resultSearch, loadingButton, selectedRowKeys } = this.state;
    const { selectedController, results, loading } = this.props;
    const rowSelection = {
      selectedRowKeys,
      onChange: this.onSelectChange,
      hideDefaultSelections: true,
      fixed: true,
    };
    const hasSelected = selectedRowKeys.length > 0;
    for (var result in results) {
      results[result]['key'] = result;
    }

    const columns = [
      {
        title: 'Result',
        dataIndex: 'run.name',
        key: 'run.name',
        sorter: (a, b) => compareByAlph(a['run.name'], b['run.name']),
      },
      {
        title: 'Config',
        dataIndex: 'run.config',
        key: 'run.config',
      },
      {
        title: 'Start Time',
        dataIndex: 'run.startRun',
        key: 'run.startRun',
        sorter: (a, b) => a['run.startRunUnixTimestamp'] - b['run.startRunUnixTimestamp'],
      },
      {
        title: 'End Time',
        dataIndex: 'run.endRun',
        key: 'run.endRun',
      },
    ];

    return (
      <PageHeaderLayout title={selectedController}>
        <Card bordered={false}>
          <Input
            style={{ width: 300, marginRight: 8, marginTop: 16 }}
            ref={ele => (this.searchInput = ele)}
            placeholder="Search Results"
            value={this.state.searchText}
            onChange={this.onInputChange}
            onPressEnter={this.onSearch}
          />
          <Button type="primary" onClick={this.onSearch}>
            {'Search'}
          </Button>
          {selectedRowKeys.length > 0 ? (
            <Card
              style={{ marginTop: 16 }}
              hoverable={false}
              title={
                <Button
                  type="primary"
                  onClick={this.onCompareResults}
                  disabled={!hasSelected}
                  loading={loadingButton}
                >
                  {'Compare Results'}
                </Button>
              }
              hoverable={false}
              type="inner"
            >
              {selectedRowKeys.map((row, i) => (
                <Tag key={i} id={row}>
                  {results[row]['run.name']}
                </Tag>
              ))}
            </Card>
          ) : (
            <div />
          )}
          <Table
            style={{ marginTop: 20 }}
            rowSelection={rowSelection}
            columns={columns}
            dataSource={resultSearch.length > 0 ? resultSearch : results}
            onRowClick={this.retrieveResults.bind(this)}
            loading={loading}
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
