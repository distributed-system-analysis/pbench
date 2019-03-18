import React, { Component } from 'react';
import { Input, Card, Row, Col, Divider, Tag, Spin } from 'antd';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';

import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import MonthSelect from '../../components/MonthSelect';
import Table from '../../components/Table';

@connect(({ search, global, loading }) => ({
  mapping: search.mapping,
  searchResults: search.searchResults,
  fields: search.fields,
  selectedFields: search.selectedFields,
  selectedIndices: global.selectedIndices,
  indices: global.indices,
  datastoreConfig: global.datastoreConfig,
  loadingMapping: loading.effects['search/fetchIndexMapping'],
  loadingSearchResults: loading.effects['search/fetchSearchResults'],
}))
export default class SearchList extends Component {
  constructor(props) {
    super(props);

    this.state = {
      searchQuery: '',
    };
  }

  componentDidMount() {
    const { selectedIndices, indices} = this.props;

    if (selectedIndices.length === 0 || indices.length === 0) {
      this.queryDatastoreConfig();      
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

  fetchMonthIndices = () => {
    const { dispatch, datastoreConfig } = this.props;

    dispatch({
      type: 'global/fetchMonthIndices',
      payload: { datastoreConfig: datastoreConfig },
    }).then(() => {
      this.fetchIndexMapping();
    });
  };

  fetchIndexMapping = () => {
    const { dispatch, datastoreConfig, indices } = this.props;

    dispatch({
      type: 'search/fetchIndexMapping',
      payload: {
        datastoreConfig: datastoreConfig,
        indices: indices,
      },
    });
  };

  resetSelectedFields = () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'search/modifySelectedFields',
      payload: ['run.name', 'run.config', 'run.controller'],
    });
  };

  clearSelectedFields = () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'search/updateSelectedFields',
      payload: [],
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
    let newSelectedFields = selectedFields.slice();

    if (newSelectedFields.includes(field)) {
      newSelectedFields.splice(newSelectedFields.indexOf(field), 1);
    } else {
      newSelectedFields.push(field);
    }

    dispatch({
      type: 'search/updateSelectedFields',
      payload: newSelectedFields,
    });
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
        datastoreConfig: datastoreConfig,
        selectedIndices: selectedIndices,
        selectedFields: selectedFields,
        query: searchQuery,
      },
    });
  };

  retrieveResults = selectedResults => {
    const { dispatch } = this.props;

    dispatch({
      type: 'dashboard/updateSelectedController',
      payload: selectedResults[0]['run.controller'],
    }).then(() => {
      dispatch({
        type: 'dashboard/updateSelectedResults',
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

  render() {
    const {
      selectedIndices,
      indices,
      mapping,
      selectedFields,
      searchResults,
      loadingSearchResults,
      loadingMapping,
    } = this.props;
    let columns = [];
    selectedFields.map(field => {
      columns.push({
        title: field,
        dataIndex: field,
        key: field,
      });
    });

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
                title={'Filters'}
                extra={
                  <div>
                    <a onClick={this.resetSelectedFields}>{'Reset'}</a>
                    <a onClick={this.clearSelectedFields} style={{ marginLeft: 16 }}>
                      {'Clear'}
                    </a>
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
                {Object.keys(mapping).map(field => {
                  return (
                    <div>
                      <p style={{ fontWeight: 'bold' }}>{field}</p>
                      <p>
                        {mapping[field].map(item => {
                          let fieldItem = field + '.' + item;
                          return (
                            <Tag
                              onClick={() => this.updateSelectedFields(fieldItem)}
                              style={{ marginTop: 8 }}
                              color={selectedFields.includes(fieldItem) ? 'blue' : '#bdbdbd'}
                            >
                              {item}
                            </Tag>
                          );
                        })}
                      </p>
                      <Divider />
                    </div>
                  );
                })}
              </Card>
            </Col>
            <Col lg={17} md={24}>
              <Card>
                <p style={{ fontWeight: 'bold' }}>
                  {searchResults.resultCount !== undefined
                    ? searchResults.resultCount + ' results'
                    : null}
                </p>
                <Table
                  style={{ marginTop: 20 }}
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
