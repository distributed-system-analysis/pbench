import React from 'react';
import { shallow } from 'enzyme';
import Table from './index';

const mockProps = {
  dataSource: [],
  columns: [{ title: 'Controller', dataIndex: 'controller', key: 'ctrl' }],
  loading: true,
};

const mockDispatch = jest.fn();
const wrapper = shallow(<Table dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of Table component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});
