import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';
import RowSelection from './index';
import Button from '../Button';

const mockProps = {
  selectedItems: ['item-1', 'item-2', 'item-3'],
  compareActionName: 'mockCompareValue',
  style: {},
  onCompare: jest.fn(),
};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<RowSelection dispatch={mockDispatch} {...mockProps} />, {
  lifecycleExperimental: true,
});

describe('test rendering of RowSelection page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
  it('check rendering', () => {
    expect(wrapper.find(Button).length).toEqual(1);
  });
  it('test interaction of Button', () => {
    const onCompare = jest.fn();
    wrapper.setProps({ onCompare });
    wrapper
      .find(Button)
      .first()
      .props()
      .onClick();
    expect(onCompare).toHaveBeenCalledTimes(1);
  });
  it('test item length of selection', () => {
    expect(wrapper.find('span').length).toEqual(1);
    expect(wrapper.find('span').text()).toEqual('Selected 3 items');
    wrapper.setProps({ selectedItems: [] });
    expect(wrapper.find('span').text()).toEqual('');
  });
});
