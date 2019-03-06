import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';

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
  summaryTocResult: [],
};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<Summary.WrappedComponent dispatch={mockDispatch} {...mockProps} />, {
  disableLifecycleMethods: true,
});

describe('test Summary page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
