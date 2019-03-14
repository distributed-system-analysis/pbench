import React from 'react';
import { shallow } from 'enzyme';

import Sharable from './index';

const mockProps = {
  store: [],
};

const mockDispatch = jest.fn();
const wrapper = shallow(<Sharable.WrappedComponent dispatch={mockDispatch} {...mockProps} />, {
  disableLifecycleMethods: true,
});

describe('test Sharable page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
