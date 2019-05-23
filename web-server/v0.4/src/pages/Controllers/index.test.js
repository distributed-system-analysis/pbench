import React from 'react';
import { shallow } from 'enzyme';
import Controllers from './index';

import Table from '@/components/Table';
import SearchBar from '@/components/SearchBar';
import MonthSelect from '@/components/MonthSelect';

const mockProps = {
  controllers: [],
  selectedIndices: [],
  indices: [],
};

const mockDispatch = jest.fn();
const wrapper = shallow(<Controllers.WrappedComponent dispatch={mockDispatch} {...mockProps} />, {
  disableLifecycleMethods: true,
});

describe('test Controllers page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });

  it('render Table component', () => {
    expect(wrapper.find(Table).length).toBe(1);
  });

  it('render SearchBar component', () => {
    expect(wrapper.find(SearchBar).length).toBe(1);
  });

  it('render MonthSelect component', () => {
    expect(wrapper.find(MonthSelect).length).toBe(1);
  });
});
