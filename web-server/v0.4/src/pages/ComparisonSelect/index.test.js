import React from 'react';
import { shallow } from 'enzyme';

import ComparisonSelect from './index';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

const mockProps = {
  selectedResults: [],
  selectedControllers: ['controller1', 'controller2'],
  iterations: [],
  iterationParams: {},
};

const mockDispatch = jest.fn();
const wrapper = shallow(
  <ComparisonSelect.WrappedComponent dispatch={mockDispatch} {...mockProps} />,
  { disableLifecycleMethods: true }
);

describe('test ComparisonSelect page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });

  it('render multiple user selected controllers', () => {
    expect(wrapper.find(PageHeaderLayout).prop('title')).toBe('controller1, controller2');
  });
});
