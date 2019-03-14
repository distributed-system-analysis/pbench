import React from 'react';
import { shallow } from 'enzyme';

import SessionPlaceholder from './index';

const mockProps = {
  store: [],
};

const mockDispatch = jest.fn();
const wrapper = shallow(
  <SessionPlaceholder.WrappedComponent dispatch={mockDispatch} {...mockProps} />,
  {
    disableLifecycleMethods: true,
  }
);

describe('test SessionPlaceholder page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
