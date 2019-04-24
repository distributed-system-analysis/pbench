import React from 'react';
import { shallow } from 'enzyme';

import Summary from './index';

const mockProps = {
  result: {
    runMetadata: [],
    hostTools: [],
  },
  selectedResults: ['test_result'],
  selectedControllers: ['test_controller'],
  iterations: [{}],
  iterationParams: {},
}

const mockDispatch = jest.fn();
const wrapper = shallow(<Summary.WrappedComponent dispatch={mockDispatch} {...mockProps} />, { disableLifecycleMethods: true });

describe('test Summary page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
