import React from 'react';
import { shallow } from 'enzyme';
import { Tag, Tabs, Breadcrumb } from 'antd';
import PageHeader, { getBreadcrumb } from './index';
import urlToList from '../_utils/pathTools';

const routerData = {
  '/dashboard/results': {
    name: 'results',
  },
  '/search': {
    name: 'search',
  },
};

const { TabPane } = Tabs;
const mockProps = {
  selectedControllers: undefined,
  tabList: ['tab1', 'tab2'],
  routes: ['/1', '/2'],
  params: 'params',
  location: { pathname: 'location' },
  breadcrumbNameMap: 'breadcrumbNameMap',
  onTabChange: jest.fn(),
};
const mockDispatch = jest.fn();
const wrapper = shallow(<PageHeader dispatch={mockDispatch} {...mockProps} />, {
  lifecycleExperimental: true,
});

describe('test getBreadcrumb', () => {
  it('getBreadcrumb name for a simple url', () => {
    expect(getBreadcrumb(routerData, '/dashboard/results').name).toEqual('results');
  });

  it('getBreadcrumb for a single path', () => {
    const urlNameList = urlToList('/search').map(url => getBreadcrumb(routerData, url).name);
    expect(urlNameList).toEqual(['search']);
  });

  it('check getBreadcrumb function implementation', () => {
    const breadcrumbNameMap = { url: { url: 'urlItem' } };
    const url = 'url';
    const breadcrumb = breadcrumbNameMap[url];
    expect(getBreadcrumb(breadcrumbNameMap, url)).toBe(breadcrumb);
  });
});

describe('test rendering of TableFilterSelection page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
  });
  it('Check functions implementation', () => {
    const wrapper2 = shallow(<PageHeader {...mockProps} />);
    const getBreadcrumbDom = jest.spyOn(wrapper.instance(), 'getBreadcrumbDom');
    const conversionBreadcrumbList = jest.spyOn(wrapper.instance(), 'conversionBreadcrumbList');
    const getBreadcrumbProps = jest.spyOn(wrapper.instance(), 'getBreadcrumbProps');
    const conversionFromLocation = jest.spyOn(wrapper.instance(), 'getBreadcrumbProps');

    wrapper2.setProps({ selectedControllers: ['a', 'b', 'c'] });
    getBreadcrumbDom();
    expect(wrapper.state('breadcrumb')).toEqual(conversionBreadcrumbList());
    expect(conversionBreadcrumbList).toHaveBeenCalled();

    expect(getBreadcrumbProps).toHaveBeenCalled();

    // eslint-disable-next-line no-unused-vars
    const { routes, params, routerLocation, breadcrumbNameMap } = getBreadcrumbProps();
    expect(wrapper.find(Breadcrumb).props()).not.toBe({});
    wrapper
      .find(Breadcrumb)
      .props()
      .itemRender('route', 'params', 'routes', 'paths');

    wrapper.setProps({ params: undefined });
    expect(conversionFromLocation).toHaveBeenCalled();
  });
  it('check functions with null props', () => {
    const conversionBreadcrumbList = jest.spyOn(wrapper.instance(), 'conversionBreadcrumbList');
    conversionBreadcrumbList();
    wrapper.setProps({ routes: undefined, location: undefined });
    expect(wrapper.instance().conversionBreadcrumbList(null)).toBe(null);
  });
  it('check with conversionFromProps', () => {
    const conversionFromProps = jest.spyOn(wrapper.instance(), 'conversionFromProps');
    wrapper.setProps({ breadcrumbList: ['item-1', 'item-2'], breadcrumbSeparator: [','] });
    conversionFromProps();
  });
  it('check rendering and change simulation', () => {
    expect(wrapper.find(Tabs).length).toEqual(1);
    expect(wrapper.find(TabPane)).toHaveLength(2);
    wrapper
      .find(Tabs)
      .at(0)
      .simulate('change', 'key1');
    expect(wrapper.instance().props.onTabChange).toHaveBeenCalled();
  });
  it('test the titleHeader', () => {
    wrapper.setProps({ selectedControllers: ['a', 'b', 'c'] });
    expect(wrapper.find('#titleheader').find(Tag)).toHaveLength(3);
  });
  it('test the tabDefaultActiveKey', () => {
    wrapper.setProps({ tabDefaultActiveKey: ['a'] });
    wrapper.setProps({ tabActiveKey: ['a', 'b'] });
    expect(wrapper.find(Tabs).props().defaultActiveKey).toEqual(['a']);
    expect(wrapper.find(Tabs).props().activeKey).toEqual(['a', 'b']);
  });
});
