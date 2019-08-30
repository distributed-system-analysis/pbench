import React from 'react';
import { shallow } from 'enzyme';
import 'jest-canvas-mock';

import RunComparison from './index';
import { parseClusteredIterations } from '../../utils/parse';

const mockProps = {
  selectedControllers: ['controller1', 'controller2'],
  selectedResults: [],
  iterationParams: {},
};
const mockLocation = {
  state: {
    iterations: [],
    clusteredGraphData: [],
  },
};

const clusteredIterations = {};
clusteredIterations.sample_metric = [
  {
    benchmark_name: 'fio',
    'throughput-sample_metric-client_hostname:all-closestsample': 0,
    'throughput-sample_metric-client_hostname:all-mean': 0,
    'throughput-sample_metric-client_hostname:all-stddevpct': 0,
  },
];
const clusterLabels = [];
clusterLabels.sample_metric = ['sample-1'];
const selectedConfig = ['benchmark-sample-1'];

const mockDispatch = jest.fn();
const wrapper = shallow(
  <RunComparison.WrappedComponent dispatch={mockDispatch} location={mockLocation} {...mockProps} />,
  { disableLifecycleMethods: true }
);

describe('test RunComparison page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });

  it('render multiple user selected controllers', () => {
    expect(wrapper.instance().props.selectedControllers).toEqual(['controller1', 'controller2']);
  });

  it('displays correct metric data', () => {
    const result = parseClusteredIterations(clusteredIterations, clusterLabels, selectedConfig);
    expect(result.tableData.sample_metric[0].primaryMetric).toEqual('sample_metric');
  });
});
