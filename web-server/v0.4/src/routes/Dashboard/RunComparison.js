import ReactJS from 'react';
import PropTypes from 'prop-types';
import { connect } from 'dva';
import axios from 'axios';
import jschart from 'jschart';
import _ from 'lodash';
import { Row, Col, Card, Select, Tabs, Spin, Tag, Table, Button, Form } from 'antd';
import { ResponsiveBar } from '@nivo/bar';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import DescriptionList from 'ant-design-pro/lib/DescriptionList';

const { Description } = DescriptionList;
const TabPane = Tabs.TabPane;
const FormItem = Form.Item;

@connect(({ global }) => ({
  datastoreConfig: global.datastoreConfig,
}))
export default class RunComparison extends ReactJS.Component {
  static propTypes = {
    iterations: PropTypes.array,
    configCategories: PropTypes.array,
    configData: PropTypes.array,
    results: PropTypes.array,
    controller: PropTypes.controller,
  };

  constructor(props) {
    super(props);

    this.state = {
      clusterLabels: [],
      timeseriesData: [],
      timeseriesDropdown: [],
      timeseriesDropdownSelected: [],
      primaryMetricIterations: [],
      clusteredGraphData: [],
      graphKeys: [],
      tableData: [],
      loading: false,
    };
  }

  componentDidMount = () => {
    this.setState({ loading: true });
    const { configCategories } = this.props.location.state;
    this.generateIterationClusters(configCategories);
  };

  componentDidUpdate = () => {
    const { tableData, timeseriesData, timeseriesDropdownSelected } = this.state;
    if (
      Object.keys(timeseriesData).length > 0 &&
      Object.keys(timeseriesDropdownSelected).length > 0
    ) {
      Object.keys(tableData).map(table => {
        const timedata = timeseriesData[table][timeseriesDropdownSelected[table]][0];
        jschart.create_jschart(
          0,
          'timeseries',
          table,
          'Cluster ' + timeseriesDropdownSelected[table],
          null,
          null,
          {
            json_object: {
              x_axis_series: timedata['x_axis_series'],
              data: timedata['data'],
              data_series_names: timedata['data_series_names'],
            },
          }
        );
      });
    }
  };

  findAggregation(key) {
    if (key.includes('all') & key.includes('mean')) {
      return key;
    }
  }

  parseGraphData = clusteredIterations => {
    const { clusterLabels } = this.state;
    var clusteredGraphData = [];
    var graphKeys = [];
    var tableData = [];
    for (var primaryMetric in clusteredIterations) {
      clusteredGraphData[primaryMetric] = [];
      graphKeys[primaryMetric] = [];
      tableData[primaryMetric] = [];
      var maxClusterLength = 0;
      for (var cluster in clusteredIterations[primaryMetric]) {
        var clusterObject = { cluster: cluster };
        for (var iteration in clusteredIterations[primaryMetric][cluster]) {
          clusterObject[iteration] =
            clusteredIterations[primaryMetric][cluster][iteration][
              Object.keys(clusteredIterations[primaryMetric][cluster][iteration]).find(
                this.findAggregation
              )
            ];
        }
        clusteredGraphData[primaryMetric].push(clusterObject);
        var clusterItems = Object.keys(clusterObject).length - 1;
        if (clusterItems > maxClusterLength) {
          maxClusterLength = clusterItems;
        }
        tableData[primaryMetric].push({
          key: cluster,
          clusterID: cluster,
          cluster: clusterLabels[primaryMetric][cluster],
          primaryMetric: primaryMetric,
          length: clusterItems,
        });
      }
      for (var i = 0; i < maxClusterLength; i++) {
        graphKeys[primaryMetric].push(i);
      }
    }
    this.setState({ tableData: tableData });
    this.setState({ graphKeys: graphKeys });
    this.setState({ clusteredGraphData: clusteredGraphData });
    this.setState({ loading: false });
  };

  groupClusters = (array, cluster, f) => {
    var groups = {};
    array.forEach(function(o) {
      var group = f(o).join('-');
      groups[group] = groups[group] || [];
      groups[group].push(o);
    });
    var { clusterLabels } = this.state;
    clusterLabels[cluster] = Object.keys(groups);
    this.setState({ clusterLabels: clusterLabels });
    return Object.keys(groups).map(function(group) {
      return groups[group];
    });
  };

  generateIterationClusters = config => {
    this.setState({ loading: true });
    this.setState({ selectedConfig: config });
    const { iterations } = this.props.location.state;
    var primaryMetricIterations = [];
    primaryMetricIterations = _.mapValues(_.groupBy(iterations, 'primary_metric'), clist =>
      clist.map(iteration => _.omit(iteration, 'primary_metric'))
    );
    var clusteredIterations = [];
    for (var cluster in primaryMetricIterations) {
      clusteredIterations = [];
      if (typeof config == 'object' && config.length > 0) {
        clusteredIterations = this.groupClusters(
          primaryMetricIterations[cluster],
          cluster,
          function(item) {
            var configData = [];
            for (var filter in config) {
              configData.push(item[config[filter]]);
            }
            return configData;
          }
        );
      } else {
        clusteredIterations = _.mapValues(
          _.groupBy(primaryMetricIterations[cluster], config),
          clist => clist.map(iteration => _.omit(iteration, config))
        );
      }
      primaryMetricIterations[cluster] = clusteredIterations;
    }
    this.setState({ primaryMetricIterations: primaryMetricIterations });
    this.retrieveTimeseriesData(primaryMetricIterations);
    this.parseGraphData(primaryMetricIterations);
  };

  resetIterationClusters = () => {
    const { configCategories } = this.props.location.state;
    this.generateIterationClusters(configCategories);
  };

  renameProp = (oldProp, newProp, { [oldProp]: old, ...others }) => {
    return {
      [newProp]: old,
      ...others,
    };
  };

  retrieveTimeseriesData(clusteredIterations) {
    const { datastoreConfig } = this.props;

    var iterationRequests = [];
    for (var primaryMetric in clusteredIterations) {
      for (var cluster in clusteredIterations[primaryMetric]) {
        for (var iteration in clusteredIterations[primaryMetric][cluster]) {
          iterationRequests.push(
            axios.get(
              datastoreConfig.results +
                '/results/' +
                encodeURIComponent(
                  clusteredIterations[primaryMetric][cluster][iteration].controller_name
                ) +
                '/' +
                encodeURIComponent(
                  clusteredIterations[primaryMetric][cluster][iteration].result_name
                ) +
                '/' +
                encodeURIComponent(
                  clusteredIterations[primaryMetric][cluster][iteration].iteration_number
                ) +
                '-' +
                encodeURIComponent(
                  clusteredIterations[primaryMetric][cluster][iteration].iteration_name
                ) +
                '/' +
                'sample' +
                encodeURIComponent(
                  clusteredIterations[primaryMetric][cluster][iteration].closest_sample
                ) +
                '/' +
                'result.json'
            )
          );
        }
      }
    }
    axios.all(iterationRequests).then(args => {
      var timeseriesData = [];
      var timeseriesDropdown = [];
      var timeseriesDropdownSelected = [];
      var responseCount = 0;
      for (var primaryMetric in clusteredIterations) {
        timeseriesData[primaryMetric] = [];
        for (var cluster in clusteredIterations[primaryMetric]) {
          timeseriesData[primaryMetric][cluster] = [];
          var iterationTimeseriesData = [];
          var timeseriesLabels = ['time'];
          for (var iteration in clusteredIterations[primaryMetric][cluster]) {
            var iterationTypes = Object.keys(args[responseCount].data);
            for (var iterationTest in iterationTypes) {
              if (
                Object.keys(args[responseCount].data[iterationTypes[iterationTest]]).includes(
                  primaryMetric
                )
              ) {
                var hosts = args[responseCount].data[iterationTypes[iterationTest]][primaryMetric];
                for (var host in hosts) {
                  if (hosts[host].client_hostname == 'all') {
                    for (var item in hosts[host].timeseries) {
                      hosts[host].timeseries[item] = this.renameProp(
                        'date',
                        'x',
                        hosts[host].timeseries[item]
                      );
                      hosts[host].timeseries[item] = this.renameProp(
                        'value',
                        'y' + (parseInt(iteration) + 1),
                        hosts[host].timeseries[item]
                      );
                    }
                    timeseriesLabels.push(
                      clusteredIterations[primaryMetric][cluster][iteration].result_name +
                        '-' +
                        clusteredIterations[primaryMetric][cluster][iteration].iteration_name
                    );
                    iterationTimeseriesData = _.merge(
                      iterationTimeseriesData,
                      hosts[host].timeseries
                    );
                    responseCount++;
                  }
                }
              }
            }
          }
          let timeLabel = timeseriesLabels.splice(0, 1)[0];
          timeseriesLabels.splice(1, 0, timeLabel);
          timeseriesData[primaryMetric][cluster].push({
            ['data_series_names']: timeseriesLabels,
            ['data']: iterationTimeseriesData.map(Object.values),
            ['x_axis_series']: 'time',
          });
        }
      }
      for (var primaryMetric in Object.keys(timeseriesData)) {
        timeseriesDropdownSelected[Object.keys(timeseriesData)[primaryMetric]] = 0;
        timeseriesDropdown[Object.keys(timeseriesData)[primaryMetric]] = Object.keys(
          timeseriesData[Object.keys(timeseriesData)[primaryMetric]]
        );
      }
      this.setState({ timeseriesData: timeseriesData });
      this.setState({ timeseriesDropdownSelected: timeseriesDropdownSelected });
      this.setState({ timeseriesDropdown: timeseriesDropdown });
    });
  }

  clusterDropdownChange = (value, primaryMetric) => {
    var { tableData, timeseriesDropdownSelected } = this.state;
    Object.keys(tableData).map(table => {
      document.getElementById(table).innerHTML = '';
    });
    timeseriesDropdownSelected[primaryMetric] = value;
    this.setState({ timeseriesDropdownSelected: timeseriesDropdownSelected });
  };

  render() {
    const { configCategories, controller, selectedResults } = this.props.location.state;
    const {
      graphKeys,
      tableData,
      clusteredGraphData,
      primaryMetricIterations,
      selectedConfig,
      timeseriesData,
      timeseriesDropdown,
      timeseriesDropdownSelected,
    } = this.state;

    const expandedRowRender = cluster => {
      var columns = [
        {
          title: 'iteration_name',
          dataIndex: 'iteration_name',
          key: 'iteration_name',
        },
        {
          title: 'result_name',
          dataIndex: 'result_name',
          width: 250,
          key: 'result_name',
        },
        {
          title: 'iteration_number',
          dataIndex: 'iteration_number',
          key: 'iteration_number',
        },
      ];
      for (var config in configCategories) {
        columns.push({
          title: configCategories[config],
          dataIndex: configCategories[config],
          key: configCategories[config],
        });
      }
      columns.push({ title: 'closest_sample', dataIndex: 'closest_sample', key: 'closest_sample' });

      return (
        <Table
          columns={columns}
          dataSource={primaryMetricIterations[cluster.primaryMetric][cluster.key]}
          pagination={false}
        />
      );
    };

    const description = (
      <div>
        <DescriptionList size="small" col="1" gutter={16}>
          <Description term="Controller">{<Tag>{controller}</Tag>}</Description>
          <Description term="Results">
            {selectedResults.map(result => (
              <Tag>{result['run.name']}</Tag>
            ))}
          </Description>
          <Description term="Clustering Config">
            <div>
              <Select
                addonBefore="Cluster Parameters"
                mode="tags"
                placeholder="Select cluster config"
                value={selectedConfig}
                defaultValue={configCategories}
                onChange={this.generateIterationClusters}
              >
                {configCategories.map((category, i) => (
                  <Select.Option value={category}>{category}</Select.Option>
                ))}
              </Select>
              <Button
                type="primary"
                onClick={this.resetIterationClusters}
                style={{ marginLeft: 8 }}
              >
                {'Reset'}
              </Button>
            </div>
          </Description>
        </DescriptionList>
      </div>
    );

    const action = (
      <div>
        <Button type="primary" onClick={window.print}>
          {'Share'}
        </Button>
      </div>
    );

    const columns = [
      {
        title: 'Cluster ID',
        dataIndex: 'clusterID',
        key: 'clusterID',
      },
      {
        title: 'Matched Configurations',
        dataIndex: 'cluster',
        render: text => {
          var splitTags = text.split('-');
          return splitTags.map((tag, i) => <Tag color="#2db7f5">{tag}</Tag>);
        },
        key: 'cluster',
      },
      {
        title: 'Iterations',
        dataIndex: 'length',
        key: 'length',
      },
    ];

    const legendColumns = [
      {
        title: 'Cluster ID',
        dataIndex: 'clusterID',
        key: 'clusterID',
      },
      {
        title: 'Matched Configurations',
        dataIndex: 'cluster',
        render: text => {
          var splitTags = text.split('-');
          return splitTags.map((tag, i) => <Tag color="#2db7f5">{tag}</Tag>);
        },
        key: 'cluster',
      },
    ];

    return (
      <div>
        <div>
          <PageHeaderLayout title="Run Comparison Details" content={description} action={action} />
        </div>
        <br />
        <Card loading={false} bordered={true} bodyStyle={{ padding: 4 }}>
          <Tabs size="large">
            <TabPane tab="Summary" key="summary" style={{ padding: 16 }}>
              <Spin spinning={this.state.loading}>
                {Object.keys(clusteredGraphData).map(cluster => (
                  <div>
                    <Row style={{ marginTop: 16 }}>
                      <Col xl={16} lg={12} md={12} sm={24} xs={24} style={{ height: 500 }}>
                        <h4 style={{ marginLeft: 16 }}>{cluster}</h4>
                        <ResponsiveBar
                          data={clusteredGraphData[cluster]}
                          keys={graphKeys[cluster]}
                          indexBy="cluster"
                          groupMode="grouped"
                          padding={0.3}
                          colors="set3"
                          animate={true}
                          motionStiffness={90}
                          motionDamping={15}
                          labelSkipWidth={18}
                          labelSkipHeight={18}
                          tooltip={({ id, index, value, color }) => (
                            <div style={{ backgroundColor: 'white', color: 'grey' }}>
                              <Row>
                                <Col>{'Result'}</Col>
                                <Col>{primaryMetricIterations[cluster][index][id].result_name}</Col>
                              </Row>
                              <br />
                              <Row>
                                <Col>{'Iteration'}</Col>
                                <Col>
                                  {primaryMetricIterations[cluster][index][id].iteration_name}
                                </Col>
                              </Row>
                              <br />
                              <Row>
                                <Col>{'Mean'}</Col>
                                <Col>{value}</Col>
                              </Row>
                              <br />
                              <Row>
                                <Col>{'Matched Configurations'}</Col>
                                <Col>
                                  <div>
                                    {tableData[cluster][index].cluster.split('-').map((tag, i) => (
                                      <Tag color="#2db7f5">{tag}</Tag>
                                    ))}
                                  </div>
                                </Col>
                              </Row>
                            </div>
                          )}
                          borderColor="inherit:darker(1.6)"
                          margin={{
                            top: 32,
                            left: 64,
                            bottom: 64,
                            right: 124,
                          }}
                          axisLeft={{
                            orient: 'left',
                            tickSize: 5,
                            tickPadding: 5,
                            tickRotation: 0,
                            legend: 'mean',
                            legendPosition: 'center',
                            legendOffset: -40,
                          }}
                          axisBottom={{
                            orient: 'bottom',
                            tickSize: 5,
                            tickPadding: 5,
                            tickRotation: 0,
                            legend: 'cluster ID',
                            legendPosition: 'center',
                            legendOffset: 36,
                          }}
                          labelTextColor="inherit:darker(1.6)"
                          theme={{
                            tooltip: {
                              container: {
                                background: 'white',
                                fontSize: '13px',
                              },
                            },
                            labels: {
                              textColor: '#555',
                            },
                          }}
                        />
                      </Col>
                      <Col xl={8} lg={12} md={12} sm={24} xs={24}>
                        <Table
                          size="small"
                          columns={legendColumns}
                          dataSource={tableData[cluster]}
                        />
                      </Col>
                    </Row>
                    <br
                      style={{
                        borderTopWidth: 1,
                        borderStyle: 'solid',
                        borderColor: '#8c8b8b',
                      }}
                    />
                  </div>
                ))}
              </Spin>
            </TabPane>
            <TabPane forceRender={true} tab="All" key="all" style={{ padding: 16 }}>
              {(Object.keys(timeseriesData).length > 0) &
              (Object.keys(timeseriesDropdown).length > 0) ? (
                <div>
                  {Object.keys(tableData).map(table => (
                    <Card
                      type="inner"
                      title={table}
                      style={{ marginBottom: 16 }}
                      extra={
                        <Form layout={'inline'}>
                          <FormItem
                            label="Selected Cluster"
                            colon={false}
                            style={{ marginLeft: 16, fontWeight: '500' }}
                          >
                            <Select
                              defaultValue={'Cluster ' + 0}
                              style={{ width: 120, marginLeft: 16 }}
                              value={timeseriesDropdownSelected[table]}
                              onChange={value => this.clusterDropdownChange(value, table)}
                            >
                              {timeseriesDropdown[table].map(cluster => (
                                <Select.Option value={cluster}>
                                  {'Cluster ' + cluster}
                                </Select.Option>
                              ))}
                            </Select>
                          </FormItem>
                        </Form>
                      }
                    >
                      <div id={table} />
                    </Card>
                  ))}
                </div>
              ) : (
                <div />
              )}
            </TabPane>
          </Tabs>
        </Card>
        <br />
        <Card title="Cluster Tables">
          {Object.keys(tableData).map(table => (
            <Table
              bordered
              title={() => <h4>{table}</h4>}
              columns={columns}
              dataSource={tableData[table]}
              expandedRowRender={expandedRowRender}
              pagination={{ pageSize: 20 }}
            />
          ))}
        </Card>
      </div>
    );
  }
}
