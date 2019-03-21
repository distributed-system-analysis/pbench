import React from 'react';
import { shallow } from 'enzyme';

import Search from './index';

const mockProps = {
  mapping: {
    "run": [],
  },
  searchResults: {
    "resultsCount": [],
    "results": [],
  },
  selectedFields: [],
  selectedIndices: [],
}

const mockDispatch = jest.fn();
const wrapper = shallow(<Search.WrappedComponent dispatch={mockDispatch} {...mockProps} />, { disableLifecycleMethods: true });

describe('test Search page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
