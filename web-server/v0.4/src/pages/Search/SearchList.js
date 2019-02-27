import ReactJS, { Component } from 'react';
import { Input, Card, Row, Col, Divider, Tag, Table, Select, Spin } from 'antd';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

const Option = Select.Option;

@connect(({ search, global, loading }) => ({
  mapping: search.mapping,
  searchResults: search.searchResults,
  fields: search.fields,
  selectedFields: search.selectedFields,
  selectedIndices: global.selectedIndices,
  selectorIndices: global.selectorIndices,
  indices: global.indices,
  datastoreConfig: global.datastoreConfig,
  loadingMapping: loading.effects['search/fetchIndexMapping'],
  loadingResults: loading.effects['search/fetchSearchResults'],
}))
export default class SearchList extends Component {
  constructor(props) {
    super(props);

    this.state = {
      searchQuery: '',
    };
  }

  componentDidMount() {
    this.queryDatastoreConfig();
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
    const { dispatch, indices } = this.props;
    let selectedIndices = [];

    value.map(item => {
      selectedIndices.push(indices[item]);
    });

    dispatch({
      type: 'search/updateSelectedIndices',
      payload: selectedIndices,
    });
    dispatch({
      type: 'global/updateSelectorIndices',
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

  retrieveResults = params => {
    const { dispatch } = this.props;

    dispatch({
      type: 'dashboard/updateSelectedController',
      payload: params['run.controller'],
    }).then(() => {
      dispatch({
        type: 'dashboard/updateSelectedResults',
        payload: params,
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
      selectorIndices,
      indices,
      mapping,
      selectedFields,
      searchResults,
      loadingResults,
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
                  <p style={{ fontWeight: 'bold' }}>{'Indices'}</p>
                  <Select
                    mode="multiple"
                    style={{ width: '100%' }}
                    placeholder="Select index"
                    value={selectorIndices}
                    onChange={this.updateSelectedIndices}
                    tokenSeparators={[',']}
                  >
                    {indices.map((index, i) => {
                      return <Select.Option key={i}>{index}</Select.Option>;
                    })}
                  </Select>
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
                  onRowClick={this.retrieveResults.bind(this)}
                  defaultPageSize={20}
                  loading={loadingMapping || loadingResults}
                  showSizeChanger={true}
                  showTotal={true}
                  pagination={{ pageSize: 20 }}
                  bordered
                />
              </Card>
            </Col>
          </Row>
        </div>
      </PageHeaderLayout>
    );
  }
}
