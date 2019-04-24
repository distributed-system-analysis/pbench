import React from 'react';
import { mount } from 'enzyme';
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
  },
};

const mockDispatch = jest.fn();
const wrapper = mount(
  <RunComparison.WrappedComponent dispatch={mockDispatch} location={mockLocation} {...mockProps} />,
  { disableLifecycleMethods: true }
);

describe('test RunComparison page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });

  it('render multiple user selected controllers', () => {
    expect(wrapper.findWhere(node => node.key() === 'controller1').length).toEqual(1);
    expect(wrapper.findWhere(node => node.key() === 'controller2').length).toEqual(1);
  });
});
