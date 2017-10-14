import React, {PropTypes} from 'react';
import history from '../../core/history';
import { Spin, Tag, Table, Input, Button, LocaleProvider} from 'antd';
import enUS from 'antd/lib/locale-provider/en_US';
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
      tables: [],
      resultJSON: [],
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

    axios.get('http://pbench.perf.lab.eng.bos.redhat.com/results/' + encodeURI(this.props.controller.slice(0, this.props.controller.indexOf("."))) +'/'+ encodeURI(this.props.result) + '/summary-result.csv').then(res => {
      this.setState({resultJSON: JSON.parse(csvJSON(res.data.replace(/(^[ \t]*\n)/gm, "")))});
      this.setState({loading: false});
    })
    .catch(function (error) {
      isSuccessful = false;
    });

    if (isSuccessful != true) {
      this.setState({loading: false});
    }
  }

  render() {
    var { summaryResult, tables, resultJSON, loading } = this.state;

    var controllerName = "controller: " + this.props.controller;
    var resultTable = [];
    const columns = [];
    var tableLength = 0;

    for (var item in resultJSON) {
      var result = resultJSON[item];
      if (result.iteration_number != "") {
        var resultObj = {};
        for (var key in result) {
          if (result.hasOwnProperty(key)) {
            columns.push({
              title: key,
              dataIndex: key,
              key: key,
            });
            tableLength += (3 * key.length);
            resultObj[key] = result[key];
          }
        }
        resultTable.push(resultObj);
      }
    }

    {/*var isColumn = false;
    var columns = [];
    var data = [];
    Object.keys(summaryResult).forEach(function (row) {
        if (row.length != 1 && isColumn == false) {
            columns = [];
            isColumn = true;
            summaryResult[row].map(function (column) {
                columns.push({
                  title: summaryResult[row][column],
                  dataIndex: column,
                  key: column
                });
            })
        } else if (row.length != 1 && isColumn == true) {
            data = [];
            summaryResult[row].map(function (data) {
                data.push({
                  data: summaryResult[row][data]
                });
            })
        } else if (row.length == 1) {
            isColumn = false;
        }
    });*/}

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
            <div className="col-sm-10 col-md-9">
              <div className="page-header page-header-bleed-right">
                <h1 id="dbstart">{this.props.result}</h1>
                <Tag color="blue" key={this.props.controller}>
                  {controllerName}
                </Tag>
                <h1 id="dbfinal" style={{ display: 'none' }}>Dashboard for <span id="script"></span> result <span id="result_name"></span></h1>
              </div>
              <Table style={{marginTop: 20}} columns={columns} dataSource={resultTable} loading={loading} scroll={{ x: tableLength * 2.25 }} title={() => 'Result Data'} size="small" bordered/>
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

function csvJSON(csv) {

  var lines = csv.split("\n");
  var result = [];
  var headers = lines[0].split(",");

  for (var i = 1; i < lines.length; i++) {
    var obj = {};
    var currentline = lines[i].split(",");

    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = currentline[j];
    }

    result.push(obj);
  }

  return JSON.stringify(result);
}

export default Summary;
