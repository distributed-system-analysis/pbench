import React from 'react';
import { connect } from 'dva';
import { Spin, Tag, Card, List, Typography, Divider } from 'antd';
import { filterIterations } from '../../utils/parse';

import PageHeaderLayout from '../../layouts/PageHeaderLayout';
import Table from '@/components/Table';
import TableFilterSelection from '@/components/TableFilterSelection';

const tabList = [
  {
    key: 'iterations',
    tab: 'Iterations',
  },
  {
    key: 'toc',
    tab: 'Table of Contents',
  },
  {
    key: 'metadata',
    tab: 'Metadata',
  },
  {
    key: 'tools',
    tab: 'Tools & Parameters',
  },
];

const tocColumns = [
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

@connect(({ global, datastore, dashboard, loading }) => ({
  iterations: dashboard.iterations,
  iterationParams: dashboard.iterationParams,
  iterationPorts: dashboard.iterationPorts,
  result: dashboard.result,
  tocResult: dashboard.tocResult,
  datastoreConfig: datastore.datastoreConfig,
  selectedControllers: global.selectedControllers,
  selectedResults: global.selectedResults,
  selectedIndices: global.selectedIndices,
  loadingSummary:
    loading.effects['dashboard/fetchIterations'] ||
    loading.effects['dashboard/fetchResult'] ||
    loading.effects['dashboard/fetchTocResult'],
}))
class Summary extends React.Component {
  constructor(props) {
    super(props);
    const { iterations } = props;

    this.state = {
      activeSummaryTab: 'iterations',
      resultIterations: iterations[0],
    };
  }

  componentDidMount() {
    const { dispatch, datastoreConfig, selectedIndices, selectedResults } = this.props;

    dispatch({
      type: 'dashboard/fetchIterations',
      payload: { selectedResults, datastoreConfig },
    });
    dispatch({
      type: 'dashboard/fetchResult',
      payload: {
        datastoreConfig,
        selectedIndices,
        result: selectedResults[0]['run.name'],
      },
    });
    dispatch({
      type: 'dashboard/fetchTocResult',
      payload: {
        datastoreConfig,
        selectedIndices,
        id: selectedResults[0].id,
      },
    });
  }

  componentWillReceiveProps(nextProps) {
    const { iterations } = this.props;

    if (nextProps.iterations !== iterations) {
      this.setState({ resultIterations: nextProps.iterations[0] });
    }
  }

  onFilterTable = (selectedParams, selectedPorts) => {
    const { iterations } = this.props;

    const filteredIterations = filterIterations(iterations, selectedParams, selectedPorts);
    this.setState({ resultIterations: filteredIterations[0] });
  };

  onTabChange = key => {
    this.setState({ activeSummaryTab: key });
  };

  render() {
    const { activeSummaryTab, resultIterations } = this.state;
    const {
      selectedResults,
      loadingSummary,
      iterationParams,
      iterationPorts,
      selectedControllers,
      tocResult,
      result,
    } = this.props;

    const contentList = {
      iterations: (
        <Card title="Result Iterations" style={{ marginTop: 32 }}>
          <Spin spinning={loadingSummary} tip="Loading Iterations...">
            <TableFilterSelection
              onFilterTable={this.onFilterTable}
              filters={iterationParams}
              ports={iterationPorts}
            />
            <Table
              style={{ marginTop: 16 }}
              columns={resultIterations ? resultIterations.columns : []}
              dataSource={resultIterations ? resultIterations.iterations : []}
              bordered
            />
          </Spin>
        </Card>
      ),
      toc: (
        <Card title="Table of Contents" style={{ marginTop: 32 }}>
          <Table columns={tocColumns} dataSource={tocResult} defaultExpandAllRows />
        </Card>
      ),
      metadata: (
        <Card title="Run Metadata" style={{ marginTop: 32 }}>
          {result.runMetadata && (
            <List
              size="small"
              bordered
              dataSource={Object.entries(result.runMetadata)}
              renderItem={([label, value]) => (
                <List.Item key={label}>
                  <Typography.Text strong>{label}</Typography.Text>
                  <Divider type="vertical" />
                  {value}
                </List.Item>
              )}
            />
          )}
        </Card>
      ),
      tools: (
        <Card title="Host Tools & Parameters" style={{ marginTop: 32 }}>
          {result.hostTools &&
            result.hostTools.map(host => (
              <List
                key={host.hostname}
                style={{ marginBottom: 16 }}
                size="small"
                bordered
                header={
                  <div>
                    <Typography.Text strong>hostname</Typography.Text>
                    <Divider type="vertical" />
                    {host.hostname}
                  </div>
                }
                dataSource={Object.entries(host.tools)}
                renderItem={([label, value]) => (
                  <List.Item key={label}>
                    <Typography.Text strong>{label}</Typography.Text>
                    <Divider type="vertical" />
                    {value}
                  </List.Item>
                )}
              />
            ))}
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
                {`controller: ${selectedControllers[0]}`}
              </Tag>
            }
            tabList={tabList}
            tabActiveKey={activeSummaryTab}
            onTabChange={this.onTabChange}
          />
          {contentList[activeSummaryTab]}
        </div>
      </div>
    );
  }
}

export default connect(() => ({}))(Summary);
