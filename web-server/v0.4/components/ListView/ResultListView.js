import React, {PropTypes} from 'react';
import history from '../../core/history';
import {Table, Input, Button, LocaleProvider} from 'antd';
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

  onSelectChange = (selectedRowKeys) => {
    this.setState({ selectedRowKeys });
  }

  getResultMetadata(key) {
    return axios.get('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + key + '" } }, "fields": [ "run.name", "run.config", "run.start_run", "run.end_run", "run.script" ], "sort": "_index" }', { cancelToken: this.cancelToken.token }).then(res => {
      this.setState({results: this.state.results.concat({result: res.data.hits.hits[0].fields['run.name'][0], config: res.data.hits.hits[0].fields['run.config'][0], startRun: res.data.hits.hits[0].fields['run.start_run'][0], endRun: res.data.hits.hits[0].fields['run.end_run'][0]})});
    });
  }

  componentWillMount() {
    this.cancelToken = CancelToken.source();
  }

  componentDidMount() {
    this.setState({loading: true});
    axios.get('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?search_type=count&source={ "query": { "match": { "run.controller": "' + this.props.controller + '" } }, "aggs": { "run": { "terms": { "field": "run.name", "size": 0 } } } }').then(res => {
      const response = res.data.aggregations.run.buckets;
      var results = [];
      for (var item in response) {
        results.push(this.getResultMetadata(response[item].key))
      }
      axios.all(results).then(axios.spread(function (results) {
      }));
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
    const {results, resultSearch, loading, loadingButton, selectedRowKeys} = this.state;
    const rowSelection = {
      selectedRowKeys,
      onChange: this.onSelectChange,
    };
    const hasSelected = selectedRowKeys.length > 0;

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
        sorter: (a, b) => a.start_time - b.start_time
      }, {
        title: 'End Time',
        dataIndex: 'endRun',
        key: 'endRun',
        sorter: (a, b) => a.end_time - b.end_time
      }
    ];

    return (
      <LocaleProvider locale={enUS}>
        <div style={{marginTop: 4}} className="container-fluid container-pf-nav-pf-vertical">
          <h1>{this.props.controller}</h1>
          <Button
            style={{marginTop: 20}}
            type="primary"
            onClick={this.start}
            disabled={!hasSelected}
            loading={loadingButton}
          >
            Compare
          </Button>
          <Input
            style={{width: 300, marginLeft: 16, marginRight: 8}}
            ref={ele => this.searchInput = ele}
            placeholder = "Search results"
            value = {this.state.searchText}
            onChange = {this.onInputChange}
            onPressEnter = {this.onSearch}
          />
          <Button type="primary" onClick={this.onSearch}>Search</Button>
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
