import React, { Component } from 'react';
import { Input, Card, Row, Form, Tag, Icon, Spin, Select, Popover, Descriptions } from 'antd';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import _ from 'lodash';

import Button from '@/components/Button';
import RowSelection from '@/components/RowSelection';
import MonthSelect from '@/components/MonthSelect';
import Table from '@/components/Table';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

@connect(({ search, global, datastore, loading }) => ({
  mapping: search.mapping,
  searchResults: search.searchResults,
  fields: search.fields,
  selectedFields: global.selectedFields,
  selectedIndices: global.selectedIndices,
  selectedResults: global.selectedResults,
  indices: datastore.indices,
  datastoreConfig: datastore.datastoreConfig,
  loadingMapping: loading.effects['search/fetchIndexMapping'],
  loadingSearchResults: loading.effects['search/fetchSearchResults'],
}))
class SearchList extends Component {
  constructor(props) {
    super(props);

    this.state = {
      searchQuery: '',
      updateFiltersDisabled: true,
      selectedRuns: [],
    };
  }

  componentDidMount() {
    const { indices, mapping, selectedIndices } = this.props;

    if (indices.length === 0 || Object.keys(mapping).length === 0 || selectedIndices.length === 0) {
      this.queryDatastoreConfig();
    }
  }

  componentDidUpdate(prevProps) {
    const { selectedResults, selectedIndices, selectedFields } = this.props;

    if (prevProps.selectedResults !== selectedResults) {
      this.setState({ selectedRuns: selectedResults });
    }
    if (
      prevProps.selectedIndices !== selectedIndices ||
      prevProps.selectedFields !== selectedFields
    ) {
      this.setState({ updateFiltersDisabled: false });
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

  onRemoveRun = selectedRowData => {
    let { selectedRuns } = this.state;

    selectedRuns = selectedRuns.filter(run => {
      if (run.key === selectedRowData.key) {
        return false;
      }
      return true;
    });

    this.setState({ selectedRuns });
  };

  onSelectChange = selectedRowData => {
    let { selectedRuns } = this.state;

    selectedRuns = [...selectedRuns, ...selectedRowData];
    selectedRuns = _.uniqBy(selectedRuns, 'key');

    this.setState({ selectedRuns });
  };

  resetSelectedFields = async () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/updateSelectedFields',
      payload: ['run.name', 'run.config', 'run.controller', '@metadata.controller_dir'],
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

  commitRunSelections = async () => {
    const { selectedRuns } = this.state;
    const { dispatch } = this.props;

    const selectedControllers = new Set([]);
    selectedRuns.forEach(run => {
      const controller = run['run.controller'];
      selectedControllers.add(controller);
    });

    dispatch({
      type: 'global/updateSelectedResults',
      payload: selectedRuns,
    });
    dispatch({
      type: 'global/updateSelectedControllers',
      payload: [...selectedControllers],
    });
  };

  fetchSearchQuery = () => {
    const { searchQuery } = this.state;
    const { dispatch, datastoreConfig, selectedFields, selectedIndices } = this.props;

    this.commitRunSelections().then(() => {
      dispatch({
        type: 'search/fetchSearchResults',
        payload: {
          datastoreConfig,
          selectedIndices,
          selectedFields,
          query: searchQuery,
        },
      });
      this.setState({ updateFiltersDisabled: true });
    });
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

    this.commitRunSelections().then(() => {
      dispatch(
        routerRedux.push({
          pathname: '/comparison-select',
        })
      );
    });
  };

  render() {
    const { selectedRuns, updateFiltersDisabled } = this.state;
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
      onSelect: (record, selected, selectedRows) => this.onSelectChange(selectedRows),
      onSelectAll: (record, selected, selectedRows) => this.onSelectChange(selectedRows),
    };

    return (
      <PageHeaderLayout
        content={
          <div>
            <div style={{ textAlign: 'center' }}>
              <Input.Search
                prefix={<Icon type="search" style={{ color: 'rgba(0,0,0,.25)' }} />}
                placeholder="Search the datastore"
                enterButton="Search"
                size="large"
                onChange={this.updateSearchQuery}
                onSearch={this.fetchSearchQuery}
                style={{ width: 522, marginBottom: 16 }}
              />
            </div>
            <Spin spinning={loadingMapping}>
              <Form
                style={{
                  padding: '24px',
                  backgroundColor: '#FAFAFA',
                  border: '1px solid #D9D9D9',
                  borderRadius: '6px',
                }}
              >
                <Row style={{ display: 'flex', flexWrap: 'wrap' }}>
                  <div style={{ marginRight: 16 }}>
                    <p style={{ marginBottom: 0, fontSize: 12, fontWeight: 600 }}>months</p>
                    <MonthSelect
                      indices={indices}
                      updateButtonVisible={false}
                      onChange={this.updateSelectedIndices}
                      value={selectedIndices}
                      style={{ width: 160 }}
                    />
                  </div>
                  {Object.keys(mapping).map(field => (
                    <div key={field}>
                      <p style={{ marginBottom: 4, fontSize: 12, fontWeight: 600 }}>{field}</p>
                      <Select
                        mode="multiple"
                        key={field}
                        placeholder={field}
                        value={selectedFields.filter(item => {
                          return item.split('.')[0] === field;
                        })}
                        onSelect={value => this.updateSelectedFields(`${field}.${value}`)}
                        onDeselect={value => this.updateSelectedFields(`${value}`)}
                        style={{ marginRight: 16, width: 160 }}
                        dropdownMatchSelectWidth={false}
                      >
                        {mapping[field].map(item => {
                          return (
                            <Select.Option value={item} label={item} key={item}>
                              {item}
                            </Select.Option>
                          );
                        })}
                      </Select>
                    </div>
                  ))}
                </Row>
                <Row>
                  <div style={{ textAlign: 'right' }}>
                    <Button
                      type="primary"
                      htmlType="submit"
                      name="Filter"
                      disabled={updateFiltersDisabled}
                      onClick={this.fetchSearchQuery}
                    />
                    <Button
                      type="secondary"
                      style={{ marginLeft: 8 }}
                      onClick={this.resetSelectedFields}
                      name="Reset"
                    />
                  </div>
                </Row>
              </Form>
            </Spin>
          </div>
        }
      >
        <div>
          <Card>
            <p style={{ fontWeight: '400', color: 'rgba(0,0,0,.50)' }}>
              {searchResults.resultCount !== undefined && `${searchResults.resultCount} hits`}
            </p>
            <RowSelection
              selectedItems={selectedRuns}
              compareActionName="Compare Results"
              onCompare={this.compareResults}
            />
            <br />
            <div style={{ display: 'flex', flex: 1, flexDirection: 'row', flexWrap: 'wrap' }}>
              {selectedRuns.map(run => {
                return (
                  <div key={run['run.id']}>
                    <Popover
                      content={
                        <Descriptions bordered column={1} size="small">
                          {columns.map(column => {
                            return (
                              <Descriptions.Item key={column.dataIndex} label={column.dataIndex}>
                                {run[column.dataIndex]}
                              </Descriptions.Item>
                            );
                          })}
                        </Descriptions>
                      }
                    >
                      <Tag
                        visible
                        style={{ marginBottom: 8 }}
                        closable
                        onClose={() => this.onRemoveRun(run)}
                      >
                        {run['run.name']}
                      </Tag>
                    </Popover>
                  </div>
                );
              })}
            </div>
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
        </div>
      </PageHeaderLayout>
    );
  }
}

export default SearchList;
