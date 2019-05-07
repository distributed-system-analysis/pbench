import React from 'react';
import { shallow } from 'enzyme';
import Results from './index';

import Table from '@/components/Table';
import RowSelection from '@/components/RowSelection';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

const mockProps = {
  selectedControllers: ['controller1'],
};

const mockDispatch = jest.fn();
const wrapper = shallow(<Results.WrappedComponent dispatch={mockDispatch} {...mockProps} />, {
  disableLifecycleMethods: true,
});

describe('test Results page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });

  it('render Table component', () => {
    expect(wrapper.find(Table).length).toBe(1);
  });

  it('render RowSelection component', () => {
    expect(wrapper.find(RowSelection).length).toBe(1);
  });

  it('render user selected controllers', () => {
    expect(wrapper.find(PageHeaderLayout).prop('title')).toBe('controller1');
  });
});
