import React, {PropTypes} from 'react';
import history from '../../core/history';
import { Select, Tabs, Spin, Divider, Tag, Table, Input, Button, LocaleProvider, Badge, Menu, Dropdown, Icon} from 'antd';
import { Bar } from "@nivo/bar";
import axios from 'axios';
import DOMParser from 'react-native-html-parser';
const TabPane = Tabs.TabPane;

class CompareIterations extends React.Component {
  static propTypes = {
    iterations: React.PropTypes.array,
    configCategories: React.PropTypes.array
  };

  constructor(props) {
    super(props);

    this.state = {
      csvData: [],
      clusteredIterations: [],
      clusteredGraphData: [],
      loading: false
    }
  }

  findAggregation(key) {
    if (key.includes("all") & key.includes("mean")) {
      return key;
    }
  }

  parseGraphData = (clusteredIterations) => {
    var clusteredGraphData = []
    for (var cluster in clusteredIterations) {
      var clusterObject = {cluster: cluster}
      for (var iteration in clusteredIterations[cluster]) {
        clusterObject[iteration] = clusteredIterations[cluster][iteration][Object.keys(clusteredIterations[cluster][iteration]).find(this.findAggregation)]
      }
      clusteredGraphData.push(clusterObject);
    }
    this.setState({clusteredGraphData: clusteredGraphData});
    this.setState({loading: false});
  }

  generateIterationClusters = (config) => {
    this.setState({loading: true})
    const { iterations } = this.props;
    var clusteredIterations = [];
    if (config.length > 0) {
      for (var item in config) {
        if (item == 0) {
          clusteredIterations = _.mapValues(_.groupBy(iterations, config[item]),
                                clist => clist.map(iteration => _.omit(iteration, config[item])));
        } else {
          clusteredIterations = _.mapValues(_.groupBy(clusteredIterations, config[item]),
                                clist => clist.map(iteration => _.omit(iteration, config[item])));
        }
      }
    } else {
      clusteredIterations = _.mapValues(_.groupBy(iterations, config),
                            clist => clist.map(iteration => _.omit(iteration, config)));
    }
    this.setState({clusteredIterations: clusteredIterations});
    this.parseGraphData(clusteredIterations);
  }

  componentDidMount() {
    this.setState({loading: true});
    const { iterations, configCategories } = this.props;
    var iterationRequests = [];
    for (var iteration in iterations) {
      iterationRequests.push(axios.get('http://pbench.perf.lab.eng.bos.redhat.com/results/' + encodeURIComponent(iterations[iteration].controller_name) + '/' + encodeURIComponent(iterations[iteration].result_name) + '/' + encodeURIComponent(iterations[iteration].iteration_number) + '-' + encodeURIComponent(iterations[iteration].iteration_name) + '/' + 'sample' + encodeURIComponent(iterations[iteration].closest_sample)
       + '/csv/' + encodeURIComponent(iterations[iteration].benchmark_name) + '_' + encodeURIComponent(iterations[iteration].primary_metric) + '.csv'))
    }
    axios.all(iterationRequests)
    .then(args => {
      var csvData = [];
      for (var data in args) {
        csvData.push(args[data].data)
      }
      this.setState({csvData: csvData})
    });
    this.generateIterationClusters(configCategories);

    const script1 = document.createElement("script");
    script1.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/d3.min.js";
    script1.async = true;

    const script2 = document.createElement("script");
    script2.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/d3-queue.min.js";
    script2.async = true;

    const script3 = document.createElement("script");
    script3.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/saveSvgAsPng.js";
    script3.async = true;

    const script4 = document.createElement("script");
    script4.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/jschart.js";
    script4.async = true;

    document.body.appendChild(script1);
    document.body.appendChild(script2);
    document.body.appendChild(script3);
    document.body.appendChild(script4);
  }

  iframe(controllerName, resultName, iterationNumber, iterationName, closestSample) {
    return {
      __html: '<iframe style="overflow: hidden; height: 600px; border: none; margin: 0; padding: 0; scrolling: none" src="http://pbench.perf.lab.eng.bos.redhat.com/results/' + controllerName + '/' + resultName + '/' + iterationNumber + '-' + iterationName + '/' + 'sample' + closestSample + '/uperf.html" width="100%" height="2000"></iframe>'
    }
  }

  graphIframe() {
    return {
      __html: '<iframe style="overflow: hidden; height: 500px; width: 1400px; border: none; margin: 0; padding: 0; scrolling: none" src="https://nivo-api.herokuapp.com/r/2f527a6d-8a46-4788-a40e-47adf14eac49"></iframe>'
    }
  }

  graphIframe2() {
    return {
      __html: '<iframe style="overflow: hidden; height: 800px; width: 1400px; border: none; margin: 0; padding: 0; scrolling: none" src="https://nivo-api.herokuapp.com/samples/line.svg"></iframe>'
    }
  }

  aggregateIframe() {
    const { csvData } = this.state;

    return {
      __html: '<script src="/static/js/v0.3/d3.min.js"></script><script src="/static/js/v0.3/d3-queue.min.js"></script><script src="/static/js/v0.3/saveSvgAsPng.js"></script><script src="/static/js/v0.3/jschart.js"></script><center><h2>sample1 - uperf</h2></center><div id="chart_1"><script>create_jschart("lineChart", "timeseries", "chart_1", "Testing", null, null, { csvfiles:' + JSON.stringify(csvData) + '})</script></div>'
    }
  }

  render() {
      const { iterations, configCategories } = this.props;
      const { csvData, clusteredGraphData, clusteredIterations } = this.state;

      var graphKeys = [];
      for (var iteration in iterations) {
        graphKeys.push(iteration.toString());
      }

      const expandedRowRender = (cluster) => {
        var columns = [{
          title: 'iteration_name',
          dataIndex: 'iteration_name',
          key: 'iteration_name'
        }, {
          title: 'iteration_number',
          dataIndex: 'iteration_number',
          key: 'iteration_number'
        }
        ];
        for (var config in configCategories) {
          columns.push({title: configCategories[config], dataIndex: configCategories[config], key: configCategories[config]});
        }

        return (
          <Table
            columns={columns}
            dataSource={clusteredIterations[cluster.key]}
            pagination={false}
          />
        );
      };

      const columns = [{
        title: 'Cluster Name',
        dataIndex: 'cluster',
        key: 'cluster'
      }, {
        title: 'Iterations',
        dataIndex: 'length',
        key: 'length',
      }];

      var tableData = [];
      for (var iteration in clusteredIterations) {
        tableData.push({
          key: iteration,
          cluster: iteration,
          length: clusteredIterations[iteration].length
        })
      }

      return (
        <div style={{ marginLeft: 70, padding: 16 }}>
          <Tabs defaultActiveKey="1">
            <TabPane tab="Summary" key="1">
              <Spin spinning={this.state.loading}>
                <Bar
                  height={600}
                  width={1000}
                  data={clusteredGraphData}
                  keys={graphKeys}
                  indexBy="cluster"
                  groupMode="grouped"
                  padding={0.3}
                  colors="set3"
                  animate={true}
                  motionStiffness={90}
                  motionDamping={15}
                  labelSkipWidth={14}
                  labelSkipHeight={16}
                  borderColor="inherit:darker(1.6)"
                  margin={{
                      "top": 32,
                      "left": 64,
                      "bottom": 64
                  }}
                  axisBottom={{
                      "orient": "bottom",
                      "tickSize": 5,
                      "tickPadding": 5,
                      "tickRotation": 0,
                      "legend": "cluster",
                      "legendPosition": "center",
                      "legendOffset": 36
                  }}
                  labelTextColor="inherit:darker(1.6)"
                >
                </Bar>
                <Select placeholder="Cluster Type" style={{marginBottom: 16, width: 160 }} onChange={this.generateIterationClusters}>
                  {configCategories.map((category, i) =>
                    <Select.Option value={category}>{category}</Select.Option>
                  )}
                </Select>
                <Table
                  bordered
                  columns={columns}
                  dataSource={tableData}
                  expandedRowRender={expandedRowRender}
                />
              </Spin>
            </TabPane>
            <TabPane tab="Individual" key="2">
              {iterations.map((iteration, i) =>
                <div>
                  <Tag style={{fontSize: 18}}>{iteration.result_name}</Tag>
                  <Tag style={{fontSize: 18}}>{iteration.iteration_number + '-' + iteration.iteration_name}</Tag>
                  <div style={{borderColor: 'white', frameBorder: 0}} dangerouslySetInnerHTML={this.iframe(iteration.controller_name, iteration.result_name, iteration.iteration_number, iteration.iteration_name, iteration.closest_sample)}/>
                </div>
              )}
            </TabPane>
            <TabPane tab="All" key="3">
              <div style={{borderColor: 'white', frameBorder: 0}} dangerouslySetInnerHTML={this.graphIframe2()}/>
            </TabPane>
          </Tabs>
        </div>
      );
  }
}

export default CompareIterations;
