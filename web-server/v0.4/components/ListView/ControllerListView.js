import React, {PropTypes} from 'react';
import history from '../../core/history';
import {Table, Input, Button, LocaleProvider} from 'antd';
import enUS from 'antd/lib/locale-provider/en_US';
import axios from 'axios';

const Search = Input.Search;

class ControllerListView extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      controllers: [],
      controllerSearch: [],
      loading: false,
      searchText: '',
      filtered: false
    };
  }

  componentDidMount() {
    this.setState({loading: true});
    axios.get('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?search_type=count&source={ "aggs": { "run": { "terms": { "field": "controller", "size": 0 } } } }').then(res => {
      const response = res.data.aggregations.run.buckets;
      var controllers = [];
      response.map(function(controller) {
        controllers.push({key: controller.key, controller: controller.key, results: controller.doc_count});
      });
      this.setState({controllers: controllers})
      this.setState({loading: false});
    });
  }

  onInputChange = (e) => {
    this.setState({ searchText: e.target.value });
  }

  onSearch = () => {
    const { searchText, controllers } = this.state;
    const reg = new RegExp(searchText, 'gi');
    var controllerSearch = controllers.slice();
    this.setState({
      filtered: !!searchText,
      controllerSearch: controllerSearch.map((record) => {
        const match = record.controller.match(reg);
        if (!match) {
          return null;
        }
        return {
          ...record,
          controller: (
            <span>
              {record.controller.split(reg).map((text, i) => (
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
      pathname: '/results',
      state: { controller: params.key }
    })
  }

  render() {
    const location = history.getCurrentLocation();
    const {controllers, controllerSearch, loading} = this.state;

    const columns = [
      {
        title: 'Controller',
        dataIndex: 'controller',
        key: 'controller',
        sorter: (a, b) => compareByAlph(a.controller, b.controller)
      }, {
        title: 'Results',
        dataIndex: 'results',
        key: 'results',
        sorter: (a, b) => a.results - b.results
      }
    ];

    return (
      <LocaleProvider locale={enUS}>
        <div style={{marginTop: 20}} className="container-fluid container-pf-nav-pf-vertical">
          <Input
            style={{width: 300, marginRight: 8}}
            ref={ele => this.searchInput = ele}
            placeholder = "Search controllers"
            value = {this.state.searchText}
            onChange = {this.onInputChange}
            onPressEnter = {this.onSearch}
          />
          <Button type="primary" onClick={this.onSearch}>Search</Button>
          <Table style={{marginTop: 20}} columns={columns} dataSource={controllerSearch.length > 0 ? controllerSearch : controllers} onRowClick={this.retrieveResults.bind(this)} loading={loading} bordered/>
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

export default ControllerListView;
