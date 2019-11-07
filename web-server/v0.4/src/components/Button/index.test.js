import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';
import Button from './index';

const mockProps = {
  name: 'mockButton',
  type: 'primary',
  disabled: false,
  onClick: jest.fn(),
};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<Button dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of Button component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
