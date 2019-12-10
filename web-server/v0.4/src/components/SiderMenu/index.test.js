import React from 'react';
import { shallow } from 'enzyme';
import DrawerMenu from 'rc-drawer/lib';
import SiderMenuWrapper from './index';
import SiderMenu from './SiderMenu';

const mockProps = {
  isMobile: true,
  collapsed: true,
};

const mockDispatch = jest.fn();
const wrapper = shallow(<SiderMenuWrapper dispatch={mockDispatch} {...mockProps} />);

describe('test rendering of Button component', () => {
  it('render SiderMenu with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
  it('mounts Drawer & Sider Menu', () => {
    wrapper.setProps({ isMobile: false });
    expect(wrapper.find(SiderMenu)).toHaveLength(1);
    wrapper.setProps({ isMobile: true });
    expect(wrapper.find(DrawerMenu)).toHaveLength(1);
  });
  it('test the Drawer Menu functions', () => {
    const onCollapse = jest.fn();
    wrapper.setProps({ isMobile: true, onCollapse });
    wrapper
      .find(DrawerMenu)
      .first()
      .props()
      .onHandleClick();
    wrapper
      .find(DrawerMenu)
      .first()
      .props()
      .onMaskClick();
    expect(onCollapse).toHaveBeenCalledTimes(2);
  });
  it('test the Sider Menu functions', () => {
    wrapper.setProps({ isMobile: true });
    expect(wrapper.find(DrawerMenu).find(SiderMenu)).toHaveLength(1);
  });
  it('test the Sider Menu collapsing', () => {
    wrapper.setProps({ isMobile: true });
    expect(
      wrapper
        .find(DrawerMenu)
        .find(SiderMenu)
        .prop('collapsed')
    ).toBe(false);
    wrapper.setProps({ isMobile: false });
    expect(wrapper.find(SiderMenu).prop('collapsed')).toBe(true);
  });
});
