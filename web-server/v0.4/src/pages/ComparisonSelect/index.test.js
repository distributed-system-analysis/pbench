import React from 'react';
import { shallow } from 'enzyme';

import ComparisonSelect from './index';

const mockProps = {
  selectedResults: [],
}

const mockDispatch = jest.fn();
const wrapper = shallow(<ComparisonSelect.WrappedComponent dispatch={mockDispatch} {...mockProps} />, { disableLifecycleMethods: true });

describe('test ComparisonSelect page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
