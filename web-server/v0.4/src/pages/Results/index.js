import React, { Component } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Card, Form } from 'antd';

import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import SearchBar from '@/components/SearchBar';
import RowSelection from '@/components/RowSelection';
import Table from '@/components/Table';
import { compareByAlph } from '../../utils/utils';

@connect(({ global, dashboard, loading }) => ({
  selectedIndices: global.selectedIndices,
  results: dashboard.results,
  selectedControllers: global.selectedControllers,
  datastoreConfig: global.datastoreConfig,
  loading: loading.effects['dashboard/fetchResults'],
}))
class Results extends Component {
  constructor(props) {
    super(props);

    this.state = {
      results: props.results,
      selectedRowKeys: [],
    };
  }

  componentDidMount() {
    const { dispatch, datastoreConfig, selectedIndices, selectedControllers } = this.props;

    dispatch({
      type: 'dashboard/fetchResults',
      payload: {
        datastoreConfig,
        selectedIndices,
        controller: selectedControllers,
      },
    });
  }

  componentWillReceiveProps(nextProps) {
    const { results } = this.props;

    if (nextProps.results !== results) {
      this.setState({ results: nextProps.results });
    }
  }

  onSelectChange = selectedRowKeys => {
    const { dispatch, results } = this.props;
    const selectedRows = [];
    selectedRowKeys.forEach(key => {
      selectedRows.push(results[key]);
    });
    this.setState({ selectedRowKeys });

    dispatch({
      type: 'global/updateSelectedResults',
      payload: selectedRows,
    });
  };

  onSearch = searchValue => {
    const { results } = this.props;
    const reg = new RegExp(searchValue, 'gi');
    const resultsSearch = results.slice();
    this.setState({
      results: resultsSearch
        .map((record) => {
          const match = record['run.name'].match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            'run.name': (
              <span key={record}>
                {record['run.name'].split(reg).map((text, index) => (
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
      type: 'global/updateSelectedResults',
      payload: params,
    });

    dispatch(
      routerRedux.push({
        pathname: '/summary',
      })
    );
  };

  render() {
    const { results, selectedRowKeys } = this.state;
    const { selectedControllers, loading } = this.props;
    const rowSelection = {
      selectedRowKeys,
      onChange: this.onSelectChange,
    };

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
        sorter: (a, b) => a.startUnixTimestamp - b.startUnixTimestamp,
      },
      {
        title: 'End Time',
        dataIndex: 'run.end',
        key: 'run.end',
      },
    ];

    return (
      <PageHeaderLayout title={selectedControllers.join(', ')}>
        <Card bordered={false}>
          <Form layout="vertical">
            <SearchBar
              style={{ marginBottom: 16 }}
              placeholder="Search results"
              onSearch={this.onSearch}
            />
            <RowSelection
              selectedItems={selectedRowKeys}
              compareActionName="Compare Results"
              onCompare={this.compareResults}
            />
          </Form>
          <Table
            style={{ marginTop: 16 }}
            rowSelection={rowSelection}
            columns={columns}
            dataSource={results}
            onRow={record => ({
              onClick: () => {
                this.retrieveResults([record]);
              },
            })}
            loading={loading}
            bordered
          />
        </Card>
      </PageHeaderLayout>
    );
  }
}

export default Results;
