import { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Tag, Card, Table, Input, Button, Icon, Form } from 'antd';
const FormItem = Form.Item;
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import { compareByAlph } from '../../utils/utils';

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
      results: [],
      selectedRowKeys: [],
      selectedRowNames: [],
      loading: false,
      loadingButton: false,
      searchText: '',
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

  componentDidUpdate(prevProps) {
    const { results } = this.props;
    const prevResults = prevProps.results;

    if (results !== prevResults) {
      this.setState({ results });
    }
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
    const resultsSearch = results.slice();
    this.setState({
      results: resultsSearch
        .map((record, i) => {
          const match = record['run.name'].match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            'run.name': (
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
        pathname: '/comparison-select',
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
        pathname: '/summary',
      })
    );
  };

  emitEmpty = () => {
    this.searchInput.focus();
    this.setState({
      results: this.props.results,
      searchText: '',
    });
  };

  render() {
    const { results, loadingButton, selectedRowKeys, searchText } = this.state;
    const { selectedController, loading } = this.props;
    const rowSelection = {
      selectedRowKeys,
      onChange: this.onSelectChange,
      hideDefaultSelections: true,
      fixed: true,
    };
    const suffix = searchText ? <Icon type="close-circle" onClick={this.emitEmpty} /> : null;
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
        dataIndex: 'run.start',
        key: 'run.start',
        sorter: (a, b) => a['startUnixTimestamp'] - b['startUnixTimestamp'],
      },
      {
        title: 'End Time',
        dataIndex: 'run.end',
        key: 'run.end',
      },
    ];

    return (
      <PageHeaderLayout title={selectedController}>
        <Card bordered={false}>
          <Form layout={'inline'} style={{ display: 'flex', flex: 1, alignItems: 'center' }}>
            <FormItem>
              <Input
                style={{ width: 300 }}
                ref={ele => (this.searchInput = ele)}
                prefix={<Icon type="search" style={{ color: 'rgba(0,0,0,.25)' }} />}
                suffix={suffix}
                placeholder="Search results"
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
          </Form>
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
            dataSource={results}
            onRow={record => ({
              onClick: () => {
                this.retrieveResults([record]);
              },
            })}
            loading={loading}
            pagination={{ pageSize: 20 }}
            bordered
          />
        </Card>
      </PageHeaderLayout>
    );
  }
}
