import * as ReactJS from 'react';
export interface IChartCardProps {
  title: ReactJS.ReactNode;
  action?: ReactJS.ReactNode;
  total?: ReactJS.ReactNode | number | (() => ReactJS.ReactNode | number);
  footer?: ReactJS.ReactNode;
  contentHeight?: number;
  avatar?: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export default class ChartCard extends ReactJS.Component<IChartCardProps, any> {}
