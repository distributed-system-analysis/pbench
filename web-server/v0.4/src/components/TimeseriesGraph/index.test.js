import React from 'react';
import { shallow, mount } from 'enzyme';
import TimeseriesGraph from './index';

const mockProps = {
  dataSeriesNames: ['name1', 'time', 'name2'],
  data: [[1, 1, 1], [2, 2, 2]],
  graphId: 'GraphId',
  graphName: 'Graph',
  graphOptions: {},
  xAxisSeries: 'time',
  xAxisTitle: 'xAxix',
  yAxisTitle: 'yAxis',
};

const mockDispatch = jest.fn();
jest.mock('jschart', () => ({
  create_jschart: jest.fn(() => {
    return 'true';
  }),
  chart_reload: jest.fn(() => {
    return 'true';
  }),
}));
const wrapper = shallow(<TimeseriesGraph dispatch={mockDispatch} {...mockProps} />, {
  lifecycleExperimental: true,
});

describe('test rendering of TimeseriesGraph page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });

  it('jschart graph id is same as props', () => {
    expect(wrapper.instance().props.graphId).toBe('GraphId');
  });

  it('jschart graph division exits', () => {
    expect(wrapper.contains(<div id={mockProps.graphId} />)).toEqual(true);
  });
});

describe('test Creation of graph', () => {
  it('jschart graph is created successfully', () => {
    const division = global.document.createElement('div');
    division.id = 'GraphId';
    global.document.body.appendChild(division);
    const container = mount(<TimeseriesGraph {...mockProps} />, { attachTo: division });
    container.debug();
    container.detach();
  });
});

describe('test Creation of graph on update', () => {
  it('component did update with diff data', () => {
    const oldProp = wrapper.instance().props;
    wrapper.setProps({ dataSeriesNames: ['nameA', 'time', 'nameB'], data: [[3, 3, 3], [4, 4, 4]] });
    const newProp = wrapper.instance().props;
    expect(newProp.data).not.toEqual(oldProp.data);
  });

  it('component did update with same data', () => {
    const oldProp = wrapper.instance().props;
    wrapper.setProps({ dataSeriesNames: ['nameA', 'time', 'nameB'], data: [[3, 3, 3], [4, 4, 4]] });
    const newProp = wrapper.instance().props;
    expect(newProp.data).toEqual(oldProp.data);
    expect(newProp.dataSeriesNames).toEqual(oldProp.dataSeriesNames);
  });
});
