import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';

import Table from '@/components/Table';
import RowSelection from '@/components/RowSelection';
import Results from './index';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

const mockProps = {
  selectedControllers: ['controller1'],
};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<Results.WrappedComponent dispatch={mockDispatch} {...mockProps} />, {
  disableLifecycleMethods: true,
});

describe('test Results page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });

  it('render Table component', () => {
    expect(wrapper.find(Table).length).toBe(2);
  });

  it('render RowSelection component', () => {
    expect(wrapper.find(RowSelection).length).toBe(1);
  });

  it('render user selected controllers', () => {
    expect(wrapper.find(PageHeaderLayout).prop('title')).toBe('controller1');
  });
});
