import React from 'react';
import { shallow, mount } from 'enzyme';
import { Input, Icon } from 'antd';
import SearchBar from './index';

const { Search } = Input;

const mockProps = {
  onSearch: jest.fn(),
  style: {
    display: 'flex',
    flexDirection: 'row',
    alignContent: 'center',
    maxWidth: 300,
  },
};

const mockDispatch = jest.fn();
const wrapper = shallow(<SearchBar dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of TableFilterSelection page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
  it('checks rendering', () => {
    expect(wrapper.find(Search).length).toEqual(1);
  });
});

describe('test interaction of SearchBar page component', () => {
  it('changes search value', () => {
    wrapper
      .find(Search)
      .at(0)
      .simulate('change', { target: { value: 'mockValue' } });
    expect(wrapper.state('searchValue')).toEqual('mockValue');
  });
  it('on search value', () => {
    const onSearch = jest.fn();
    wrapper.setProps({ onSearch });
    wrapper
      .find(Search)
      .first()
      .props()
      .onSearch();
    expect(onSearch).toHaveBeenCalledTimes(1);
  });
  it('renders Icon if search value is not empty', () => {
    wrapper.setState({ searchValue: 'abc' });
    expect(wrapper.find(Search).props().suffix.props).not.toBe({});
  });
  it('click on empty icon', () => {
    const emitEmpty = jest.spyOn(wrapper.instance(), 'emitEmpty');
    const click = mount(<Icon type="close-circle" onClick={emitEmpty} label="test" />);
    click.find(Icon).prop('onClick')();
    expect(emitEmpty).toHaveBeenCalled();
  });
});
