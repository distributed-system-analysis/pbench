import ReactJS from 'react';
import { connect } from 'dva';
import { Select, Spin, Tag, Table, Button, Card, notification } from 'antd';
import cloneDeep from 'lodash/cloneDeep';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import { queryIterations } from '../../services/dashboard';
import { parseIterationData } from '../../utils/parse';

const tabList = [
  {
    key: 'iterations',
    tab: 'Iterations',
  },
  {
    key: 'metadata',
    tab: 'Metadata',
  },
  {
    key: 'tools',
    tab: 'Tools & Parameters',
  },
  {
    key: 'toc',
    tab: 'Table of Contents',
  },
];

const columns = [
  {
    title: 'Name',
    dataIndex: 'name',
    key: 'name',
    width: '60%',
  },
  {
    title: 'Size',
    dataIndex: 'size',
    key: 'size',
    width: '20%',
  },
  {
    title: 'Mode',
    dataIndex: 'mode',
    key: 'mode',
  },
];

@connect(({ global, dashboard, loading }) => ({
  selectedControllers: global.selectedControllers,
  selectedResults: global.selectedResults,
  iterations: dashboard.iterations,
  summaryResult: dashboard.result,
  results: dashboard.results,
  datastoreConfig: global.datastoreConfig,
  selectedIndices: global.selectedIndices,
  controllers: dashboard.controllers,
  tocResult: dashboard.tocResult,
}))
class Summary extends ReactJS.Component {
  constructor(props) {
    super(props);

    this.fileData = [];

    this.state = {
      summaryResult: [],
      iterations: [],
      iterationSearch: [],
      columns: [],
      configData: {},
      selectedConfig: [],
      responseData: {},
      selectedPort: 'all',
      ports: [],
      loading: true,
      searchText: '',
      activeTab: 'iterations',
      tocTree: [],
      file: [],
    };
  }

  componentDidMount() {
    this.setState({ loading: true });
    const {
      dispatch,
      datastoreConfig,
      selectedIndices,
      selectedResults,
      selectedControllers,
    } = this.props;

    if (!Array.isArray(selectedResults)) {
      throw new Error("selectedResults is not an array!");
    }
    else if (selectedResults.length <= 0) {
      throw new Error("no selectedResults!");
    }
    else if (selectedResults.length > 1) {
      throw new Error("too many selectedResults!");
    }

    dispatch({
      type: 'dashboard/fetchResult',
      payload: {
        datastoreConfig: datastoreConfig,
        selectedIndices: selectedIndices,
        result: selectedResults[0]['run.name'],
      },
    });
    dispatch({
      type: 'dashboard/fetchTocResult',
      payload: {
        datastoreConfig: datastoreConfig,
        selectedIndices: selectedIndices,
        id: selectedResults[0]['id'],
      },
    });

    if (selectedResults[0]['run.controller'] != selectedControllers[0]) {
      throw new Error(
        "Logic bomb! selected results controller, "
          + selectedResults[0]['run.controller']
          + " != selected controller "
          + selectedControllers[0]);
    }
    queryIterations({ selectedResults: selectedResults, datastoreConfig: datastoreConfig })
      .then(res => {
        let parsedIterationData = parseIterationData(res);
        this.setState({
          responseData: parsedIterationData.responseData,
          ports: parsedIterationData.ports,
          configData: parsedIterationData.configData,
          loading: false,
        });
      })
      .catch(err => {
        console.log("queryIterations: error processing iteration data: '" + err + "'");
        console.log(err);
        this.openNetworkErrorNotification('error');
        this.setState({ loading: false });
      });
  }

  openNetworkErrorNotification = type => {
    notification[type]({
      message: 'Network Error',
      description: 'Unable to find an associated result file. Please try another result.',
    });
  };

  containsKey(columns, item) {
    var contains = false;
    for (var column in columns) {
      if (columns[column].key == item) {
        return true;
      }
      var keys = Object.keys(columns[column]);
      for (var key in keys) {
        if (keys[key] == 'children') {
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
        if (keys[key] == 'children') {
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

  onInputChange = e => {
    this.setState({ searchText: e.target.value });
  };

  onSearch = () => {
    const { searchText, iterations } = this.state;
    const reg = new RegExp(searchText, 'gi');
    var iterationSearch = iterations.slice();
    this.setState({
      filtered: !!searchText,
      iterationSearch: iterationSearch
        .map(record => {
          const match = record.iteration_name.match(reg);
          if (!match) {
            return null;
          }
          return {
            ...record,
            iteration_name: (
              <span>
                {record.iteration_name
                  .split(reg)
                  .map(
                    (text, i) =>
                      i > 0 ? [<span style={{ color: 'orange' }}>{match[0]}</span>, text] : text
                  )}
              </span>
            ),
          };
        })
        .filter(record => !!record),
    });
  };

  configChange = (value, category) => {
    var { selectedConfig } = this.state;
    if (value == undefined) {
      delete selectedConfig[category];
    } else {
      selectedConfig[category] = value;
    }
    this.setState({ selectedConfig: selectedConfig });
  };

  clearFilters = () => {
    this.setState({
      selectedConfig: [],
      selectedPort: 'all',
    });
  };

  portChange = value => {
    this.setState({ selectedPort: value });
    if (value == 'all') {
      this.forceUpdate();
    }
  };

  insertTreeData = (items = [], [head, ...tail]) => {
    const { tocResult } = this.props;
    if (tocResult['/' + [head, ...tail].join('/')] != undefined) {
      this.fileData[tail[tail.length - 1]] = tocResult['/' + [head, ...tail].join('/')];
    }
    let child = items.find(child => child.name === head);
    if (!child) {
      if (this.fileData[head] != undefined) {
        items.push(
          (child = {
            name: head,
            key: Math.random(),
            size: this.fileData[head][0],
            mode: this.fileData[head][1],
            children: [],
          })
        );
      } else {
        items.push((child = { name: head, key: Math.random(), children: [] }));
      }
    }
    if (tail.length > 0) {
      this.insertTreeData(child.children, tail);
    } else {
      delete child.children;
    }
    return items;
  };

  onTabChange = key => {
    const { tocResult } = this.props;
    let newstate = { activeTab: key };
    if (key == 'toc') {
      let tocTree = Object.keys(tocResult)
        .map(path => path.split('/').slice(1))
        .reduce((items, path) => this.insertTreeData(items, path), []);
      newstate['tocTree'] = tocTree;
    }
    this.setState(newstate);
  };

  list(data) {
    const children = items => {
      if (items) {
        return this.list(items);
      }
    };

    return data.map((node, index) => {
      if (node.children.length == 0) {
        return (
          <TreeNode title={node.name} isLeaf>
            {children(node.children)}
          </TreeNode>
        );
      } else {
        return <TreeNode title={node.name}>{children(node.children)}</TreeNode>;
      }
    });
  }

  render() {
    var {
      responseData,
      loading,
      selectedConfig,
      selectedPort,
      ports,
      configData,
      activeTab,
      tocTree,
    } = this.state;
    const { selectedResults, summaryResult, selectedControllers, tocResult } = this.props;

    if (Array.isArray(summaryResult)) {
      // console.log("summaryResult is not supposed to be an array!");
      return <Spin />;
    }
    else if (Object.keys(summaryResult).length <= 0) {
      // console.log("No keys for summaryResult");
      return <Spin />;
    }
    else if (!Array.isArray(responseData)) {
      // console.log("responseData is not an array!");
      return <Spin />;
    }
    else if (responseData.length <= 0) {
      // console.log('no responseData when we have a summaryResult dictionary!');
      return <div>result.json not found!</div>;
    }
    else if (responseData.length > 1) {
      throw new Error('Logic Bomb!  Unexpectedly received too many response data sets.');
    }

    var responseDataCopy = {};
    responseDataCopy['columns'] = cloneDeep(responseData[0].columns);
    responseDataCopy['iterations'] = cloneDeep(responseData[0].iterations);
    responseDataCopy['resultName'] = cloneDeep(responseData[0].resultName);

    var responseColumns = responseDataCopy.columns;
    var responseIterations = responseDataCopy.iterations;
    for (var column in responseColumns) {
      if (responseColumns[column]['children'] != undefined) {
        for (var networkColumn in responseColumns[column]['children']) {
          if (responseColumns[column]['children'][networkColumn]['children'] != undefined) {
            for (var portColumn in responseColumns[column]['children'][networkColumn]['children']) {
              if (
                !responseColumns[column]['children'][networkColumn]['children'][portColumn][
                  'title'
                ].includes(selectedPort)
              ) {
                responseColumns[column]['children'][networkColumn]['children'].splice(
                  portColumn,
                  1
                );
              }
            }
          }
        }
      }
      var selectedConfigLength = Object.keys(selectedConfig).length;
      if (selectedConfigLength > 0) {
        var filteredResponseData = [];
        for (var iteration in responseIterations) {
          var found = [];
          for (var config in selectedConfig) {
            if (
              (selectedConfig[config] !== undefined) &
              (selectedConfig[config] == responseIterations[iteration][config])
            ) {
              found.push(true);
            }
          }
          if (found.length == selectedConfigLength) {
            filteredResponseData.push(responseIterations[iteration]);
          }
        }
        responseDataCopy.iterations = filteredResponseData;
      }
    }

    var metadataTag = '';
    const hostTools = summaryResult._source.host_tools_info;

    if (typeof summaryResult._source['@metadata'] !== 'undefined') {
      metadataTag = '@metadata';
    } else {
      metadataTag = '_metadata';
    }

    const contentList = {
      iterations: (
        <Card title="Result Iterations" style={{ marginTop: 32 }}>
          <Button onClick={this.clearFilters}>Clear Filters</Button>
          <br />
          <Select
            allowClear={true}
            placeholder="Filter Hostname & Port"
            style={{ marginTop: 16, width: 160 }}
            onChange={this.portChange}
          >
            {ports.map((port, i) => (
              <Select.Option value={port}>{port}</Select.Option>
            ))}
          </Select>
          {Object.keys(configData).map((category, i) => (
            <Select
              key={i}
              allowClear={true}
              placeholder={category}
              style={{ marginLeft: 8, width: 160 }}
              value={selectedConfig[category]}
              onChange={value => this.configChange(value, category)}
            >
              {ports.map((port, i) => (
                <Select.Option key={i} value={port}>{port}</Select.Option>
              ))}
            </Select>
            ))}
          {Object.keys(configData).map((category, i) => (
            <Select
              key={i}
              allowClear={true}
              placeholder={category}
              style={{ marginLeft: 8, width: 160 }}
              value={selectedConfig[category]}
              onChange={value => this.configChange(value, category)}
            >
              {configData[category].map((categoryData, i) => (
                <Select.Option key={i} value={categoryData}>{categoryData}</Select.Option>
              ))}
            </Select>
          ))}
          <Table
            style={{ marginTop: 16 }}
            loading={loading}
            columns={responseDataCopy.columns}
            dataSource={responseDataCopy.iterations}
            bordered
            pagination={{ pageSize: 20 }}
          />
        </Card>
        ),
      metadata: (
        <Card title="Result Metadata" style={{ marginTop: 32 }}>
          <ul className="list-group">
            <li className="list-group-item">
              <h5 className="list-group-item-heading">Script</h5>
              <p className="list-group-item-text" id="script">
                {summaryResult._source.run.script}
              </p>
            </li>
            <li className="list-group-item">
              <h5 className="list-group-item-heading">Configuration</h5>
              <p className="list-group-item-text" id="config">
                {summaryResult._source.run.config}
              </p>
            </li>
            <li className="list-group-item">
              <h5 className="list-group-item-heading">Controller</h5>
              <p className="list-group-item-text" id="controller">
                {summaryResult._source.run.controller}
              </p>
            </li>
            <li className="list-group-item">
              <h5 className="list-group-item-heading">File Name</h5>
              <p
                className="list-group-item-text"
                style={{ overflowWrap: 'break-word' }}
                id="file_name"
              >
                {summaryResult._source[metadataTag]['file-name']}
              </p>
            </li>
            <li className="list-group-item">
              <h5 className="list-group-item-heading">Pbench Agent Version</h5>
              <p className="list-group-item-text" id="pbench_version">
                {summaryResult._source[metadataTag]['pbench-agent-version']}
              </p>
            </li>
            <li className="list-group-item">
              <h5 className="list-group-item-heading">Indexer Name</h5>
              <p className="list-group-item-text" id="generated_by">
                {summaryResult._source[metadataTag]['generated-by']}
              </p>
            </li>
            <li className="list-group-item">
              <h5 className="list-group-item-heading">Indexer Version</h5>
              <p className="list-group-item-text" id="generated_by_version">
                {summaryResult._source[metadataTag]['md5']}
              </p>
            </li>
          </ul>
        </Card>
      ),
      tools: (
        <Card title="Tools and Parameters" style={{ marginTop: 32 }}>
          {hostTools.map((host, i) => (
            <div key={i}>
              <br />
              <li className="list-group-item">
                <h5 className="list-group-item-heading">Host</h5>
                <p className="list-group-item-text">{host.hostname}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">mpstat</h5>
                <p className="list-group-item-text">{host.tools.mpstat}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">perf</h5>
                <p className="list-group-item-text">{host.tools.perf}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">proc-interrupts</h5>
                <p className="list-group-item-text">{host.tools['proc-interrupts']}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">proc-vmstat</h5>
                <p className="list-group-item-text">{host.tools['proc-vmstat']}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">sar</h5>
                <p className="list-group-item-text">{host.tools.sar}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">pidstat</h5>
                <p className="list-group-item-text">{host.tools.pidstat}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">turbostat</h5>
                <p className="list-group-item-text">{host.tools.turbostat}</p>
              </li>
              <li className="list-group-item">
                <h5 className="list-group-item-heading">iostat</h5>
                <p className="list-group-item-text">{host.tools.iostat}</p>
              </li>
            </div>
          ))}
        </Card>
      ),
      toc: (
        <Card title="Table of Contents" style={{ marginTop: 32 }}>
          <Table columns={columns} dataSource={tocTree} defaultExpandAllRows />
        </Card>
      ),
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <div>
          <PageHeaderLayout
            title={selectedResults[0]['run.name']}
            content={
              <Tag color="blue" key={selectedControllers[0]}>
                {'controller: ' + selectedControllers[0]}
              </Tag>
            }
            tabList={tabList}
            tabActiveKey={activeTab}
            onTabChange={this.onTabChange}
          />
          {contentList[activeTab]}
        </div>
      </div>
    );
  }
}

export default connect(() => ({}))(Summary);
