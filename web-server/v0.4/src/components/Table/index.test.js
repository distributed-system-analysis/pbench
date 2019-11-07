import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';
import Table from './index';

const mockProps = {
  dataSource: [],
  columns: [{ title: 'Controller', dataIndex: 'controller', key: 'ctrl' }],
  loading: true,
};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<Table dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of Table component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
