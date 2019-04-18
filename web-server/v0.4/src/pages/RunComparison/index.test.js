import React from 'react';
import { shallow } from 'enzyme';
import 'jest-canvas-mock';

import RunComparison from './index';

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
});
