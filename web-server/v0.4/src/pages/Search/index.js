import React, { Component } from 'react';
import { Input, Card, Row, Col, Divider, Tag, Spin } from 'antd';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';

import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import Button from '@/components/Button';
import RowSelection from '@/components/RowSelection';
import MonthSelect from '@/components/MonthSelect';
import Table from '@/components/Table';

@connect(({ search, global, loading }) => ({
  mapping: search.mapping,
  searchResults: search.searchResults,
  fields: search.fields,
  selectedFields: global.selectedFields,
  selectedIndices: global.selectedIndices,
  indices: global.indices,
  datastoreConfig: global.datastoreConfig,
  loadingMapping: loading.effects['search/fetchIndexMapping'],
  loadingSearchResults: loading.effects['search/fetchSearchResults'],
}))
class SearchList extends Component {
  constructor(props) {
    super(props);

    this.state = {
      searchQuery: '',
      updateFiltersDisabled: true,
      selectedRowKeys: [],
    };
  }

  componentDidMount() {
    const { mapping } = this.props;

    this.queryDatastoreConfig().then(() => {
      if (Object.keys(mapping).length === 0) {
        this.fetchIndexMapping();
      }
    });
  }

  componentWillReceiveProps(nextProps, prevProps) {
    const { selectedIndices, selectedFields } = this.props;

    if (
      selectedIndices !== prevProps.selectedIndices ||
      selectedFields !== prevProps.selectedFields
    ) {
      this.setState({ updateFiltersDisabled: false });
    }
  }

  queryDatastoreConfig = () => {
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
      this.fetchIndexMapping();
    });
  };

  fetchIndexMapping = () => {
    const { dispatch, datastoreConfig, indices } = this.props;

    dispatch({
      type: 'search/fetchIndexMapping',
      payload: {
        datastoreConfig,
        indices,
      },
    });
  };

  onRowSelectChange = (selectedRowKeys, selectedRows) => {
    const { dispatch } = this.props;
    const selectedControllers = [];
    selectedRows.forEach(row => {
      const controller = row['run.controller'];
      if (!selectedControllers.includes(controller)) {
        selectedControllers.push(controller);
      }
    });
    this.setState({ selectedRowKeys });

    dispatch({
      type: 'global/updateSelectedResults',
      payload: selectedRows,
    });
    dispatch({
      type: 'global/updateSelectedControllers',
      payload: selectedControllers,
    });
  };

  resetSelectedFields = async () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/updateSelectedFields',
      payload: ['run.name', 'run.config', 'run.controller'],
    });
  };

  updateSelectedIndices = value => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/updateSelectedIndices',
      payload: value,
    });
  };

  updateSelectedFields = field => {
    const { dispatch, selectedFields } = this.props;
    const newSelectedFields = selectedFields.slice();

    if (newSelectedFields.includes(field)) {
      newSelectedFields.splice(newSelectedFields.indexOf(field), 1);
    } else {
      newSelectedFields.push(field);
    }

    dispatch({
      type: 'global/updateSelectedFields',
      payload: newSelectedFields,
    });
    this.setState({ updateFiltersDisabled: false });
  };

  updateSearchQuery = e => {
    this.setState({ searchQuery: e.target.value });
  };

  fetchSearchQuery = () => {
    const { searchQuery } = this.state;
    const { dispatch, datastoreConfig, selectedFields, selectedIndices } = this.props;

    dispatch({
      type: 'search/fetchSearchResults',
      payload: {
        datastoreConfig,
        selectedIndices,
        selectedFields,
        query: searchQuery,
      },
    });
    dispatch({
      type: 'global/updateSelectedResults',
      payload: [],
    });
    this.setState({ selectedRowKeys: [] });
    this.setState({ updateFiltersDisabled: true });
  };

  retrieveResults = selectedResults => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/updateSelectedControllers',
      payload: [selectedResults[0]['run.controller']],
    }).then(() => {
      dispatch({
        type: 'global/updateSelectedResults',
        payload: selectedResults,
      }).then(() => {
        dispatch(
          routerRedux.push({
            pathname: '/summary',
          })
        );
      });
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

  render() {
    const { selectedRowKeys, updateFiltersDisabled } = this.state;
    const {
      selectedIndices,
      indices,
      mapping,
      selectedFields,
      searchResults,
      loadingSearchResults,
      loadingMapping,
    } = this.props;
    const columns = [];

    selectedFields.forEach(field => {
      columns.push({
        title: field,
        dataIndex: field,
        key: field,
      });
    });

    const rowSelection = {
      selectedRowKeys,
      onChange: this.onRowSelectChange,
    };

    return (
      <PageHeaderLayout
        content={
          <div style={{ textAlign: 'center' }}>
            <Input.Search
              placeholder="Search the datastore"
              enterButton
              size="large"
              onChange={this.updateSearchQuery}
              onSearch={this.fetchSearchQuery}
              style={{ width: 522 }}
            />
          </div>
        }
      >
        <div>
          <Row gutter={24}>
            <Col lg={7} md={24}>
              <Card
                title="Filter Results"
                extra={
                  <div>
                    <Button name="Reset" size="small" onClick={this.resetSelectedFields} />
                    <Button
                      name="Apply"
                      type="primary"
                      size="small"
                      disabled={updateFiltersDisabled}
                      onClick={this.fetchSearchQuery}
                      style={{ marginLeft: 16 }}
                    />
                  </div>
                }
                style={{ marginBottom: 24 }}
              >
                <Spin spinning={loadingMapping}>
                  <MonthSelect
                    indices={indices}
                    updateButtonVisible={false}
                    onChange={this.updateSelectedIndices}
                    value={selectedIndices}
                  />
                  <Divider />
                </Spin>
                {Object.keys(mapping).map(field => (
                  <div key={field}>
                    <p style={{ fontWeight: 'bold' }}>{field}</p>
                    <p>
                      {mapping[field].map(item => {
                        const fieldItem = `${field}.${item}`;
                        return (
                          <Tag
                            key={fieldItem}
                            onClick={() => this.updateSelectedFields(fieldItem)}
                            style={{ marginTop: 8 }}
                            color={selectedFields.includes(fieldItem) && 'blue'}
                          >
                            {item}
                          </Tag>
                        );
                      })}
                    </p>
                    <Divider />
                  </div>
                ))}
              </Card>
            </Col>
            <Col lg={17} md={24}>
              <Card>
                <p style={{ fontWeight: 'bold' }}>
                  {searchResults.resultCount !== undefined
                    ? `${searchResults.resultCount} hits`
                    : null}
                </p>
                <RowSelection
                  selectedItems={selectedRowKeys}
                  compareActionName="Compare Results"
                  onCompare={this.compareResults}
                />
                <Table
                  style={{ marginTop: 20 }}
                  rowSelection={rowSelection}
                  columns={columns}
                  dataSource={searchResults.results}
                  onRow={record => ({
                    onClick: () => {
                      this.retrieveResults([record]);
                    },
                  })}
                  loading={loadingSearchResults}
                />
              </Card>
            </Col>
          </Row>
        </div>
      </PageHeaderLayout>
    );
  }
}

export default SearchList;
