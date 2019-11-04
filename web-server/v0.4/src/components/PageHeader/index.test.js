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
  selectedControllers: ['a', 'b'],
  tabList: ['tab1', 'tab2'],
  routes: ['/1', '/2'],
  params: 'params',
  location: { pathname: 'location' },
  breadcrumbNameMap: 'breadcrumbNameMap',
  onTabChange: jest.fn(),
  title: 'Titel',
};
const mockDispatch = jest.fn();
const breadcrumbNameMap = { url: { url: 'urlItem' } };
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
    const url = 'url';
    const breadcrumb = breadcrumbNameMap[url];
    expect(getBreadcrumb(breadcrumbNameMap, url)).toBe(breadcrumb);
  });
});

describe('test rendering of TableFilterSelection page component', () => {
  it('render with empty props', () => {
    expect(wrapper).toMatchSnapshot();
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
  it('should render selected controllers in titleheader', () => {
    expect(wrapper.find('#titleheader').find(Tag)).toHaveLength(2);
    wrapper.setProps({ selectedControllers: undefined });
    expect(wrapper.find('#titleheader').find(Tag)).toHaveLength(0);
  });
  it('test the tabDefaultActiveKey', () => {
    wrapper.setProps({ tabDefaultActiveKey: ['a'] });
    wrapper.setProps({ tabActiveKey: ['a', 'b'] });
    expect(wrapper.find(Tabs).props().defaultActiveKey).toEqual(['a']);
    expect(wrapper.find(Tabs).props().activeKey).toEqual(['a', 'b']);
  });
});
describe('Check function implementation', () => {
  // const wrapper2 = shallow(<PageHeader {...mockProps} />);
  const getBreadcrumbDom = jest.spyOn(wrapper.instance(), 'getBreadcrumbDom');
  const conversionBreadcrumbList = jest.spyOn(wrapper.instance(), 'conversionBreadcrumbList');
  const getBreadcrumbProps = jest.spyOn(wrapper.instance(), 'getBreadcrumbProps');
  const conversionFromLocation = jest.spyOn(wrapper.instance(), 'getBreadcrumbProps');

  it('should assign breadcrumb state ', () => {
    getBreadcrumbDom();
    expect(wrapper.state('breadcrumb')).toEqual(conversionBreadcrumbList());
  });
  it('should call conversionBreadcrumbList', () => {
    expect(conversionBreadcrumbList).toHaveBeenCalled();
    expect(conversionFromLocation).toHaveBeenCalled();
  });
  it('should call getBreadcrumbProps', () => {
    wrapper.setProps({ breadcrumbList: ['breadcrumb1'] });
    expect(getBreadcrumbProps).toHaveBeenCalled();
    expect(wrapper.find(Breadcrumb).props()).not.toBe({});
  });
  it('should check itemRender prop', () => {
    wrapper
      .find(Breadcrumb)
      .props()
      .itemRender('route', 'params', 'routes', 'paths');
  });
  it('should call conversionFromProps', () => {
    const conversionFromProps = jest.spyOn(wrapper.instance(), 'conversionFromProps');
    wrapper.setProps({ breadcrumbList: ['item-1', 'item-2'], breadcrumbSeparator: [','] });
    conversionBreadcrumbList();
    expect(conversionFromProps).toHaveBeenCalled();
  });
  it('should call conversionFromLocation', () => {
    wrapper.setProps({ params: undefined, breadcrumbList: undefined });
    expect(conversionFromLocation).toHaveBeenCalled();
    wrapper.instance().conversionFromLocation(mockProps.location, breadcrumbNameMap);
    expect(wrapper.find(Breadcrumb).props()).not.toBe({});
  });
  it('check functions with null props', () => {
    conversionBreadcrumbList();
    wrapper.setProps({ routes: undefined, location: undefined, breadcrumbList: undefined });
    expect(wrapper.instance().conversionBreadcrumbList(null)).toBe(null);
  });
});
