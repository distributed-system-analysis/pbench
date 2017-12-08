import React, {PropTypes} from 'react';
import history from '../../core/history';
import { Spin, Tag, Table, Input, Button, LocaleProvider} from 'antd';
import enUS from 'antd/lib/locale-provider/en_US';
import axios from 'axios';
import DOMParser from 'react-native-html-parser';

class Summary extends React.Component {
  static propTypes = {
    result: React.PropTypes.string,
    controller: React.PropTypes.string
  };

  constructor(props) {
    super(props);

    this.state = {
      summaryResult: [],
      tables: [],
      iterations: [],
      columns: [],
      loading: false
    }
  }

   componentDidMount() {
    var isSuccessful = false;
    this.setState({loading: true});
    axios.get('http://es-perf44.perf.lab.eng.bos.redhat.com:9280/dsa.pbench.*/_search?source={ "query": { "match": { "run.name": "' + this.props.result + '" } }, "sort": "_index" }').then(res => {
      var result = [];
      result.push(res.data.hits.hits[0]);
      this.setState({summaryResult: result});
    });

    axios.get('http://pbench.perf.lab.eng.bos.redhat.com/results/' + encodeURI(this.props.controller.slice(0, this.props.controller.indexOf("."))) +'/'+ encodeURI(this.props.result) + '/result.json').then(res => {
      const response = res.data;
      this.parseJSONData(response);
      this.setState({loading: false});
    })
    .catch(function (error) {
      console.log(error);
      isSuccessful = false;
    });

    if (isSuccessful != true) {
      this.setState({loading: false});
    }
  }

  retrieveResults(params) {
    history.push({
      pathname: '/results/summary',
      state: {
        result: params.result,
        controller: this.props.controller
      }
    })
  }

  parseJSONData(response) {
    var columns = [{
      title: 'Iteration Number',
      dataIndex: 'iteration_number',
      key: 'iteration_number'
    }, {
      title: 'Iteration Name',
      dataIndex: 'iteration_name',
      key: 'iteration_name'
    }];
    var iterations = [];

    for (var iteration in response) {
      var iterationObject = {key: iteration, iteration_name: response[iteration].iteration_name, iteration_number: response[iteration].iteration_number};
      for (var iterationType in response[iteration].iteration_data) {
        if (iterationType != "parameters") {
          if (!this.containsTitle(columns, iterationType)) {
            columns.push({title: iterationType});
          } else {
            for (var iterationNetwork in (response[iteration].iteration_data[iterationType])) {
              if (!this.containsTitle(columns, iterationNetwork)) {
                var parentColumnIndex = this.getColumnIndex(columns, iterationType);
                columns[parentColumnIndex]["children"] = [{title: iterationNetwork}];
                for (var iterationData in (response[iteration].iteration_data[iterationType][iterationNetwork])) {
                  var columnTitle = "client_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].client_hostname + "-server_hostname:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_hostname + "-server_port:" + response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].server_port;
                  if (!this.containsTitle(columns, columnTitle)) {
                    var childColumnIndex = this.getChildColumnIndex(columns, iterationNetwork);
                    if (childColumnIndex == undefined) {
                      childColumnIndex = 0;
                    }
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
                          columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "mean", dataIndex: columnMean, key: columnMean}];
                          iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].mean;
                      } else {
                          columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "mean", dataIndex: columnMean, key: columnMean});
                          iterationObject[columnMean] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                      }
                    }
                    if (!this.containsKey(columns, columnStdDev)) {
                      if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                          columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "stddevpct", dataIndex: columnStdDev, key: columnStdDev}];
                          iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData].stddevpct;
                      } else {
                          columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "stddevpct", dataIndex: columnStdDev, key: columnStdDev});
                          iterationObject[columnStdDev] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                      }
                    }
                    if (!this.containsKey(columns, columnSample)) {
                      if (columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] == undefined) {
                          columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"] = [{title: "closest sample", dataIndex: columnSample, key: columnSample}];
                          iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                      } else {
                          columns[parentColumnIndex].children[childColumnIndex].children[dataChildColumnIndex]["children"].push({title: "closest sample", dataIndex: columnSample, key: columnSample});
                          iterationObject[columnSample] = response[iteration].iteration_data[iterationType][iterationNetwork][iterationData]['closest sample'];
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
      iterations.push(iterationObject);
    };

    this.setState({columns: columns});
    this.setState({iterations: iterations});
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
          this.containsKey(columns[column].children, item);
        }
      }
    }
    return contains;
  }

  getChildColumnIndex(columns, item) {
    for (var column in columns) {
      if (columns[column].title == item) {
        return column;
      }
      var keys = Object.keys(columns[column]);
      for (var key in keys) {
        if (keys[key] == "children") {
          this.getChildColumnIndex(columns[column].children, item);
        }
      }
    }
  }

  getColumnIndex(columns, item) {
    for (var column in columns) {
      if (columns[column].title == item) {
          return column;
      }
    }
  }

  render() {
    var { summaryResult, tables, columns, iterations, loading } = this.state;

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
          <div className="row">
            <div className="col-sm-10 col-md-9" style={{position: 'relative', overflow: 'auto'}}>
              <div className="page-header page-header-bleed-right">
                <h1 id="dbstart">{this.props.result}</h1>
                <Tag color="blue" key={this.props.controller}>
                  {controllerName}
                </Tag>
                <h1 id="dbfinal" style={{ display: 'none' }}>Dashboard for <span id="script"></span> result <span id="result_name"></span></h1>
              </div>
              <Table style={{marginTop: 20}} columns={columns} dataSource={iterations} onRowClick={this.retrieveResults.bind(this)} loading={loading} bordered/>
            </div>
            <div className="col-sm-4 col-md-3 sidebar-pf sidebar-pf-right">
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
                  <p className="list-group-item-text" id="file_name">{summaryResult[0]._source[metadataTag]['file-name']}</p>
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
        </div>
      );
    } else {
      return (
        <Spin></Spin>
      );
    }
  }
}

export default Summary;
