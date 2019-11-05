import React from 'react';
import { shallow, configure } from 'enzyme';
import Adapter from 'enzyme-adapter-react-16';
import { Form, Select } from 'antd';
import MonthSelect from './index';

const FormItem = Form.Item;

const mockProps = {
  indices: ['1', '2', '3'],
  value: ['0'],
  onChange: jest.fn(),
  reFetch: jest.fn(),
};

const mockDispatch = jest.fn();
configure({ adapter: new Adapter() });
const wrapper = shallow(<MonthSelect dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of MonthSelect component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
  it('checks rendering', () => {
    expect(wrapper.find(FormItem).length).toEqual(2);
    expect(wrapper.find('#update').length).toEqual(1);
  });
});

describe('test interaction within MonthSelect component', () => {
  it('check month update', () => {
    const onUpdateMonth = jest.spyOn(wrapper.instance(), 'onUpdateMonth');
    wrapper
      .find('Select')
      .at(0)
      .simulate('change', ['month1', 'month2']);
    expect(onUpdateMonth).toHaveBeenCalled();
    expect(mockProps.onChange).toHaveBeenCalled();
    expect(wrapper.state('updateDisabled')).toEqual(false);
    wrapper
      .find(Select)
      .at(0)
      .simulate('change', []);
    expect(mockProps.onChange).toHaveBeenCalled();
  });
  it('check re-fetch function', () => {
    wrapper
      .find('#update')
      .props()
      .onClick();
    expect(wrapper.find('#update').length).toEqual(1);
    expect(mockProps.reFetch).toHaveBeenCalled();
    expect(wrapper.state('updateDisabled')).toEqual(true);
  });
  it('check when update button is not visible', () => {
    wrapper.setProps({ updateButtonVisible: false });
    expect(wrapper.find(FormItem).length).toEqual(1);
  });
});
