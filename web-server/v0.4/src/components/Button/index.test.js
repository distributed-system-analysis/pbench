import React from 'react';
import { shallow } from 'enzyme';
import Button from './index';

const mockProps = {
  name: 'mockButton',
  type: 'primary',
  disabled: false,
  onClick: jest.fn(),
};

const mockDispatch = jest.fn();
const wrapper = shallow(<Button dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of Button component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
