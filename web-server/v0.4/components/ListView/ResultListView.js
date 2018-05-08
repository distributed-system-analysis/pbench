import React, {PropTypes} from 'react';
import history from '../../core/history';
import {notification, Card, Tag, Table, Input, Button, LocaleProvider} from 'antd';
import enUS from 'antd/lib/locale-provider/en_US';
import axios, { CancelToken } from 'axios';

const Search = Input.Search;

class ResultListView extends React.Component {
  static propTypes = {
    controller: React.PropTypes.string
  };

  constructor(props) {
    super(props);

    this.state = {
      results: [],
      resultSearch: [],
      selectedRowKeys: [],
      loading: false,
      loadingButton: false,
      searchText: '',
      filtered: false
    };
  }

  start = () => {
    this.setState({ loadingButton: true });
    setTimeout(() => {
      this.setState({
        selectedRowKeys: [],
        loadingButton: false,
      });
    }, 1000);
  }

  openNotificationWithIcon = (type) => {
    notification[type]({
      message: 'Please select two results for comparison.',
      placement: 'bottomRight'
    });
  }

  onCompareResults = () => {
    const { selectedRowKeys, results } = this.state;
    const { controller } = this.props;
    if (selectedRowKeys.length != 2) {
      this.openNotificationWithIcon('error')
    } else {
      var selectedResults = [];
      for (var item in selectedRowKeys) {
        var result = results[selectedRowKeys[item]];
        result["controller"] = controller;
        selectedResults.push(results[selectedRowKeys[item]])
      }
      this.compareResults(selectedResults)
    }
  }

  onSelectChange = (selectedRowKeys) => {
    this.setState({ selectedRowKeys });
  }

  getResultMetadata(key) {
    return axios.get('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + key + '" } }, "fields": [ "run.name", "run.config", "run.start_run", "run.end_run", "run.script" ]}', { cancelToken: this.cancelToken.token }).then(res => {
      this.setState({results: this.state.results.concat({result: res.data.hits.hits[0].fields['run.name'][0], config: res.data.hits.hits[0].fields['run.config'][0], startRunUnixTimestamp: Date.parse(res.data.hits.hits[0].fields['run.start_run'][0]), startRun: res.data.hits.hits[0].fields['run.start_run'][0], endRun: res.data.hits.hits[0].fields['run.end_run'][0]})});
    });
  }

  componentWillMount() {
    this.cancelToken = CancelToken.source();
  }

  componentDidMount() {
    this.setState({loading: true});
    axios.get('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?search_type=count&source={ "query": { "match": { "run.controller": "' + this.props.controller + '" } }, "aggs": { "run": { "terms": { "field": "run.name", "size": 0 } } } }').then(res => {
      var response = res.data.aggregations.run.buckets;
      response.reverse();
      var results = [];
      for (var item in response) {
        results.push(this.getResultMetadata(response[item].key))
      }
      this.setState({loading: false});
    }).catch(error => {
      console.log(error);
      this.setState({loading: false});
    });
  }

  componentWillUnmount() {
    this.cancelToken.cancel('Operation canceled by the user.');
  }

  onInputChange = (e) => {
    this.setState({ searchText: e.target.value });
  }

  onSearch = () => {
    const { searchText, results } = this.state;
    const reg = new RegExp(searchText, 'gi');
    var resultSearch = results.slice();
    this.setState({
      filtered: !!searchText,
      resultSearch: resultSearch.map((record) => {
        const match = record.result.match(reg);
        if (!match) {
          return null;
        }
        return {
          ...record,
          result: (
            <span>
              {record.result.split(reg).map((text, i) => (
                i > 0 ? [<span style={{color: 'orange'}}>{match[0]}</span>, text] : text
              ))}
            </span>
          )
        }
      }).filter(record => !!record),
    });
  }

  compareResults = (params) => {
    history.push({
      pathname: '/dashboard/results/comparison',
      state: {
        results: params
      }
    })
  }

  retrieveResults(params) {
    history.push({
      pathname: '/dashboard/results/summary',
      state: {
        result: params.result,
        controller: this.props.controller
      }
    })
  }

  render() {
    const location = history.getCurrentLocation();
    const { resultSearch, loading, loadingButton, selectedRowKeys} = this.state;
    var {results} = this.state;
    const rowSelection = {
      selectedRowKeys,
      onChange: this.onSelectChange,
      hideDefaultSelections: true,
      fixed: true
    };
    const hasSelected = selectedRowKeys.length > 0;
    results.sort(function (a, b) {
      return b.startRunUnixTimestamp - a.startRunUnixTimestamp;
    });

    const columns = [
      {
        title: 'Result',
        dataIndex: 'result',
        key: 'result',
        sorter: (a, b) => compareByAlph(a.result, b.result)
      }, {
        title: 'Config',
        dataIndex: 'config',
        key: 'config',
        sorter: (a, b) => compareByAlph(a.config, b.config)
      }, {
        title: 'Start Time',
        dataIndex: 'startRun',
        key: 'startRun',
        sorter: (a, b) => a.startRunUnixTimestamp - b.startRunUnixTimestamp
      }, {
        title: 'End Time',
        dataIndex: 'endRun',
        key: 'endRun'
      }
    ];

    return (
      <LocaleProvider locale={enUS}>
        <div style={{marginTop: 4}} className="container-fluid container-pf-nav-pf-vertical">
          <h1>{this.props.controller}</h1>
          <Input
            style={{width: 300, marginRight: 8, marginTop: 16}}
            ref={ele => this.searchInput = ele}
            placeholder = "Search Results"
            value = {this.state.searchText}
            onChange = {this.onInputChange}
            onPressEnter = {this.onSearch}
          />
          <Button type="primary" onClick={this.onSearch}>Search</Button>
          {selectedRowKeys.length > 0 ?
            <Card style={{marginTop: 16}} hoverable={false} title={<Button type="primary" onClick={this.onCompareResults} disabled={!hasSelected} loading={loadingButton}>Compare Results</Button>} hoverable={false} type="inner">
              {selectedRowKeys.map((row,i) =>
                <Tag id={row}>{results[row].result}</Tag>
              )}
            </Card>
            :
            <div></div>
          }
          <Table style={{marginTop: 20}} rowSelection={rowSelection} columns={columns} dataSource={resultSearch.length > 0 ? resultSearch: results} onRowClick={this.retrieveResults.bind(this)} loading={loading} bordered/>
        </div>
      </LocaleProvider>
    )
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

export default ResultListView;
