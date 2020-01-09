import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';
import Table from '@/components/Table';
import Explore from './index';

const mockProps = {};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<Explore.WrappedComponent dispatch={mockDispatch} {...mockProps} />, {
  disableLifecycleMethods: true,
});

describe('test Explore page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
});

describe('test delete session feature', () => {
  it('render of Table component', () => {
    expect(wrapper.find(Table).length).toEqual(1);
  });
  it('render of the edit session description columns', () => {
    expect(wrapper.find(Table).props().columns.length).toEqual(5);
    expect(wrapper.find(Table).props().columns[3].title).toEqual('Edit');
  });
});
