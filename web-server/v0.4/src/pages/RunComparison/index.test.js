import React from 'react';
import { shallow } from 'enzyme';
import 'jest-canvas-mock';

import RunComparison from './index';

const mockLocation = {
  state: {
    configCategories: [], controller: "", selectedResults: [], iterations: [],
  },
}

const mockDispatch = jest.fn();
const wrapper = shallow(<RunComparison.WrappedComponent dispatch={mockDispatch} location={mockLocation} />);

describe('test RunComparison page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
