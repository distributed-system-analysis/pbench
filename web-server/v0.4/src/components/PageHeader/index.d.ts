import * as ReactJS from 'react';
export interface IPageHeaderProps {
  title?: ReactJS.ReactNode | string;
  logo?: ReactJS.ReactNode | string;
  action?: ReactJS.ReactNode | string;
  content?: ReactJS.ReactNode;
  extraContent?: ReactJS.ReactNode;
  routes?: any[];
  params?: any;
  breadcrumbList?: Array<{ title: ReactJS.ReactNode; href?: string }>;
  tabList?: Array<{ key: string; tab: ReactJS.ReactNode }>;
  tabActiveKey?: string;
  tabDefaultActiveKey?: string;
  onTabChange?: (key: string) => void;
  tabBarExtraContent?: ReactJS.ReactNode;
  linkElement?: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export default class PageHeader extends ReactJS.Component<IPageHeaderProps, any> {}
