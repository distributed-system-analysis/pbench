import React, {PropTypes} from 'react';
import history from '../../core/history';
import { Spin, Tag, Table, Input, Button, LocaleProvider} from 'antd';
import axios from 'axios';

class Summary extends React.Component {
  static propTypes = {
    result: React.PropTypes.string,
    controller: React.PropTypes.string
  };

  constructor(props) {
    super(props);

    this.state = {
      summaryResult: [],
      iterations: [],
      iterationSearch: [],
      columns: [],
      loading: true,
      searchText: ''
    }
  }

   componentDidMount() {
    this.setState({loading: true});
    axios.get('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + this.props.result + '" } }, "sort": "_index" }').then(res => {
      var result = [];
      result.push(res.data.hits.hits[0]);
      this.setState({summaryResult: result});
    });

    axios.get('http://pbench.perf.lab.eng.bos.redhat.com/results/' + encodeURI(this.props.controller.slice(0, this.props.controller.indexOf("."))) +'/'+ encodeURI(this.props.result) + '/result.json').then(res => {
      const response = res.data;
      this.parseJSONData(response);
    })
    .catch(error => {
      console.log(error);
      this.setState({loading: false});
    });
  }

  retrieveResults(params) {
    history.push({
      pathname: '/dashboard/results/' + this.props.controller.slice(0, this.props.controller.indexOf(".")) + '/' + this.props.result + '/'+ params[1].iteration_number + '-' + params[1].iteration_name + '/sample' + params[0],
      state: {
        result: this.props.result,
        controller: this.props.controller,
        iteration_name: params[1].iteration_number + '-' + params[1].iteration_name,
        sample: 'sample' + params[0]
      }
    })
  }

  parseJSONData(response) {
    var columns = [{
      title: 'Iteration Number',
      dataIndex: 'iteration_number',
      fixed: 'left',
      width: 115,
      key: 'iteration_number',
      sorter: (a, b) => compareByAlph(a.iteration_number, b.iteration_number)
    }, {
      title: 'Iteration Name',
      dataIndex: 'iteration_name',
      fixed: 'left',
      width: 150,
      key: 'iteration_name',
      sorter: (a, b) => compareByAlph(a.iteration_name, b.iteration_name)
    }];
    var iterations = [];

    for (var iteration in response) {
      var iterationObject = {key: iteration, iteration_name: response[iteration].iteration_name, iteration_number: response[iteration].iteration_number};
      for (var iterationType in response[iteration].iteration_data) {
        if (iterationType != "parameters") {
          if (!this.containsTitle(columns, iterationType)) {
            columns.push({title: iterationType});
          }
          for (var iterationNetwork in (response[iteration].iteration_data[iterationType])) {
            var parentColumnIndex = this.getColumnIndex(columns, iterationType);
            if (!this.containsIteration(columns[parentColumnIndex], iterationNetwork)) {
              if (columns[parentColumnIndex]["children"] == undefined) {
                columns[parentColumnIndex]["children"] = [{title: iterationNetwork}];
              } else {
                columns[parentColumnIndex]["children"].push({title: iterationNetwork});
              }
              for (var iterationData in (response[iteration].iteration_data[iterationType][iterationNetwork])) {
                var columnTitle = "client_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].client_hostname + "-server_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_hostname + "-server_port:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_port;
                if (columns[parentColumnIndex]["children"] == undefined) {
                  var childColumnIndex = 0;
                } else {
                  var childColumnIndex = this.getColumnIndex(columns[parentColumnIndex].children, iterationNetwork);
                }
                if (!this.containsIteration(columns[parentColumnIndex].children[childColumnIndex], columnTitle)) {
                  if (columns[parentColumnIndex].children[childColumnIndex]["children"] == undefined) {
                    columns[parentColumnIndex].children[childColumnIndex]["children"] = [{title: columnTitle}];
                  } else {
                    columns[parentColumnIndex].children[childColumnIndex]["children"].push({title: columnTitle});
                  }
                  var columnMean = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "mean";
                  var columnStdDev = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "stddevpct";
                  var columnSample = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "closestsample";
                  var dataChildColumnIndex = this.getColumnIndex(columns[parentColumnIndex].children[childColumnIndex]["children"], columnTitle);
                  if (dataChildColumnIndex == undefined) {
                    dataChildColumnIndex = 0;
                  }
                  if (!this.containsKey(columns, columnMean)) {
                    if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "mean", dataIndex: columnMean, key: columnMean, sorter: (a, b) => a[columnMean] - b[columnMean]}];
                        iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].mean;
                    } else {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "mean", dataIndex: columnMean, key: columnMean, sorter: (a, b) => a[columnMean] - b[columnMean]});
                        iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].mean;
                    }
                  }
                  if (!this.containsKey(columns, columnStdDev)) {
                    if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "stddevpct", dataIndex: columnStdDev, key: columnStdDev, sorter: (a, b) => a[columnStdDev] - b[columnStdDev]}];
                        iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].stddevpct;
                    } else {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "stddevpct", dataIndex: columnStdDev, key: columnStdDev, sorter: (a, b) => a[columnStdDev] - b[columnStdDev]});
                        iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].stddevpct;
                    }
                  }
                  if (!this.containsKey(columns, columnSample)) {
                    if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "closest sample", dataIndex: columnSample, key: columnSample, sorter: (a, b) => a[columnSample] - b[columnSample], render: (text, record) => {
                            return (
                              <a onClick={() => this.retrieveResults([text, record])}>{text}</a>
                            );
                          },
                        }];
                        iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                    } else {
                        columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "closest sample", dataIndex: columnSample, key: columnSample, sorter: (a, b) => a[columnSample] - b[columnSample], render: (text, record) => {
                            return (
                              <a onClick={() => this.retrieveResults([text, record])}>{text}</a>
                            );
                          },
                        });
                        iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                    }
                  }
                }
              }
            } else {
              for (var iterationData in (response[iteration].iteration_data[iterationType][iterationNetwork])) {
                var columnTitle = "client_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].client_hostname + "-server_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_hostname + "-server_port:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_port;
                var columnMean = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "mean";
                var columnStdDev = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "stddevpct";
                var columnSample = iterationType + "-" + iterationNetwork + "-" + columnTitle + "-" + "closestsample";
                iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].mean;
                iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].stddevpct;
                iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
              }
            }
          }
        }
      }
      iterations.push(iterationObject);
    };
    this.setState({columns: columns});
    this.setState({iterations: iterations});
    this.setState({loading: false});
  }

  containsKey(columns, item) {
    var contains = false;
    for (var column in columns) {
      if (columns[column].key == item) {
        return true;
      }
      var keys = Object.keys(columns[column]);
      for (var key in keys) {
        if (keys[key] == "children") {
          this.containsKey(columns[column].children, item);
        }
      }
    }
    return contains;
  }

  containsTitle(columns, item) {
    var contains = false;
    for (var column in columns) {
      if (columns[column].title == item) {
        return true;
      }
      var keys = Object.keys(columns[column]);
      for (var key in keys) {
        if (keys[key] == "children") {
          this.containsTitle(columns[column].children, item);
        }
      }
    }
    return contains;
  }

  containsIteration(columns, item) {
    if (columns.children == undefined) {
      return false;
    }
    var contains = false;
    for (var column in columns.children) {
      if (columns.children[column].title == item) {
        return true;
      }
    }
    return contains;
  }

  getColumnIndex(columns, item) {
    for (var column in columns) {
      if (columns[column].title == item) {
          return column;
      }
    }
  }

  onInputChange = (e) => {
    this.setState({ searchText: e.target.value });
  }

  onSearch = () => {
    const { searchText, iterations } = this.state;
    const reg = new RegExp(searchText, 'gi');
    var iterationSearch = iterations.slice();
    this.setState({
      filtered: !!searchText,
      iterationSearch: iterationSearch.map((record) => {
        const match = record.iteration_name.match(reg);
        if (!match) {
          return null;
        }
        return {
          ...record,
          iteration_name: (
            <span>
              {record.iteration_name.split(reg).map((text, i) => (
                i > 0 ? [<span style={{color: 'orange'}}>{match[0]}</span>, text] : text
              ))}
            </span>
          )
        }
      }).filter(record => !!record),
    });
  }

  render() {
    var { summaryResult, columns, iterations, loading, iterationSearch } = this.state;

    var controllerName = "controller: " + this.props.controller;

    if (summaryResult.length > 0 && Object.keys(summaryResult[0]).length !== 0) {
      var fileName = '';
      var metadataTag = '';
      const hostTools = summaryResult[0]._source.host_tools_info;

      if (typeof summaryResult[0]._source['@metadata'] !== 'undefined') {
          metadataTag = '@metadata';
      } else {
          metadataTag = '_metadata';
      }
      return (
        <div style={{ marginLeft: 80 }} className="container-fluid">
          <Spin spinning={loading}>
            <div className="row" style={{display: 'flex'}}>
              <div className="col-sm-10 col-md-9" style={{position: 'relative', overflow: 'auto'}}>
                <div className="page-header page-header-bleed-right">
                  <h1 id="dbstart">{this.props.result}</h1>
                  <Tag color="blue" key={this.props.controller}>
                    {controllerName}
                  </Tag>
                  <h1 id="dbfinal" style={{ display: 'none' }}>Dashboard for <span id="script"></span> result <span id="result_name"></span></h1>
                </div>
                <Input
                  style={{width: 300, marginRight: 8}}
                  ref={ele => this.searchInput = ele}
                  placeholder = "Search iteration names"
                  value = {this.state.searchText}
                  onChange = {this.onInputChange}
                  onPressEnter = {this.onSearch}
                />
                <Button type="primary" onClick={this.onSearch}>Search</Button>
                <Table style={{marginTop: 20}} columns={columns} dataSource={iterationSearch.length > 0 ? iterationSearch : iterations} onRowClick={this.retrieveResults.bind(this)} scroll={{ x: 1500 }} bordered/>
              </div>
              <div className="col-sm-3  sidebar-pf sidebar-pf-right">
                <div className="sidebar-header sidebar-header-bleed-left sidebar-header-bleed-right">
                  <h2 className="h5">Result Metadata</h2>
                </div>
                <ul className="list-group">
                  <li className="list-group-item">
                    <h3 className="list-group-item-heading">Script</h3>
                    <p className="list-group-item-text" id="script">{summaryResult[0]._source.run.script}</p>
                  </li>
                  <li className="list-group-item">
                    <h3 className="list-group-item-heading">Configuration</h3>
                    <p className="list-group-item-text" id="config">{summaryResult[0]._source.run.config}</p>
                  </li>
                  <li className="list-group-item">
                    <h3 className="list-group-item-heading">Controller</h3>
                    <p className="list-group-item-text" id="controller">{summaryResult[0]._source.run.controller}</p>
                  </li>
                  <li className="list-group-item">
                    <h3 className="list-group-item-heading">File Name</h3>
                    <p className="list-group-item-text" style={{overflowWrap: 'break-word'}} id="file_name">{summaryResult[0]._source[metadataTag]['file-name']}</p>
                  </li>
                  <li className="list-group-item">
                    <h3 className="list-group-item-heading">Pbench Agent Version</h3>
                    <p className="list-group-item-text" id="pbench_version">{summaryResult[0]._source[metadataTag]['pbench-agent-version']}</p>
                  </li>
                  <li className="list-group-item">
                    <h3 className="list-group-item-heading">Indexer Name</h3>
                    <p className="list-group-item-text" id="generated_by">{summaryResult[0]._source[metadataTag]['generated-by']}</p>
                  </li>
                  <li className="list-group-item">
                    <h3 className="list-group-item-heading">Indexer Version</h3>
                    <p className="list-group-item-text" id="generated_by_version">{summaryResult[0]._source[metadataTag]['md5']}</p>
                  </li>
                </ul>
                <div className="sidebar-header sidebar-header-bleed-left sidebar-header-bleed-right">
                  <h2 className="h5">Tools and Parameters</h2>
                </div>
                  <ul className="list-group">
                {hostTools.map((host, i) =>
                  <div key={i}>
                    <br></br>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">Host</h3>
                      <p className="list-group-item-text">{host.hostname}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">mpstat</h3>
                      <p className="list-group-item-text">{host.tools.mpstat}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">perf</h3>
                      <p className="list-group-item-text">{host.tools.perf}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">proc-interrupts</h3>
                      <p className="list-group-item-text">{host.tools['proc-interrupts']}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">proc-vmstat</h3>
                      <p className="list-group-item-text">{host.tools['proc-vmstat']}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">sar</h3>
                      <p className="list-group-item-text">{host.tools.sar}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">pidstat</h3>
                      <p className="list-group-item-text">{host.tools.pidstat}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">turbostat</h3>
                      <p className="list-group-item-text">{host.tools.turbostat}</p>
                    </li>
                    <li className="list-group-item">
                      <h3 className="list-group-item-heading">iostat</h3>
                      <p className="list-group-item-text">{host.tools.iostat}</p>
                    </li>
                  </div>
                )}
                </ul>
              </div>
            </div>
          </Spin>
        </div>
      );
    } else {
      return (
        <Spin></Spin>
      );
    }
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

export default Summary;
