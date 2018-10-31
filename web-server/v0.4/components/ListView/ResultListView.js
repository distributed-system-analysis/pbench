import React from 'react';
import PropTypes from 'prop-types';
import history from '../../core/history';
import datastore from '../../utils/datastore';
import {notification, Card, Tag, Table, Input, Button, LocaleProvider} from 'antd';
import enUS from 'antd/lib/locale-provider/en_US';
import axios from 'axios';

class ResultListView extends React.Component {
  static propTypes = {
    controller: PropTypes.string
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
      var selectedResults = [];
      for (var item in selectedRowKeys) {
        var result = results[selectedRowKeys[item]];
        result["controller"] = controller;
        selectedResults.push(results[selectedRowKeys[item]])
      }
      this.compareResults(selectedResults)
  }

  onSelectChange = (selectedRowKeys) => {
    this.setState({ selectedRowKeys });
  }

  componentDidMount() {
    this.setState({loading: true});
    const { controller } = this.props;
    let data = localStorage.getItem(controller);

    if (!data) {
      axios.post(datastore.elasticsearch + datastore.prefix + datastore.run_indices,
      {
          "fields": [
            "run.controller",
            "run.start_run",
            "run.end_run",
            "run.name",
            "run.config",
          ],
          "sort": {
            "run.end_run": {
              "order": "desc",
              "ignore_unmapped": true
            }
          },
          "query": {
            "term": {
              "run.controller": controller
            }
          },
          "size": 5000
      }).then(res => {
        var res = res.data.hits.hits;
        var results = [];
        for (var response in res) {
          results.push({result: res[response].fields['run.name'][0], config: res[response].fields['run.config'][0], startRunUnixTimestamp: Date.parse(res[response].fields['run.start_run'][0]), startRun: res[response].fields['run.start_run'][0], endRun: res[response].fields['run.end_run'][0]})
        }
        this.setState({results: results})
        this.setState({loading: false})
        localStorage.setItem(controller, JSON.stringify(results))
      }).catch(error => {
        console.log(error);
        this.setState({loading: false});
      });
    } else {
        this.setState({results: JSON.parse(data)})
        this.setState({loading: false})
    }
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
        results: params,
        controller: this.props.controller
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
    const { resultSearch, loading, loadingButton, selectedRowKeys} = this.state;
    var {results} = this.state;
    const rowSelection = {
      selectedRowKeys,
      onChange: this.onSelectChange,
      hideDefaultSelections: true,
      fixed: true
    };
    const hasSelected = selectedRowKeys.length > 0;
    for (var result in results) {
      results[result]["key"] = result;
    }

    const columns = [
      {
        title: 'Result',
        dataIndex: 'result',
        key: 'result',
        sorter: (a, b) => compareByAlph(a.result, b.result)
      }, {
        title: 'Config',
        dataIndex: 'config',
        key: 'config'
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
          <h1 style={{marginTop: 8}}>{this.props.controller}</h1>
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
