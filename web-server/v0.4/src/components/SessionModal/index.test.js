import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';
import SessionModal from './index';

const mockProps = {
  store: {},
};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<SessionModal dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of SessionModal component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
