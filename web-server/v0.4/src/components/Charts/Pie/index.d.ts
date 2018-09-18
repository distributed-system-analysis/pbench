import * as ReactJS from 'react';
export interface IPieProps {
  animate?: boolean;
  color?: string;
  height: number;
  hasLegend?: boolean;
  padding?: [number, number, number, number];
  percent?: number;
  data?: Array<{
    x: string | string;
    y: number;
  }>;
  total?: ReactJS.ReactNode | number | (() => ReactJS.ReactNode | number);
  title?: ReactJS.ReactNode;
  tooltip?: boolean;
  valueFormat?: (value: string) => string | ReactJS.ReactNode;
  subTitle?: ReactJS.ReactNode;
}

export default class Pie extends ReactJS.Component<IPieProps, any> {}
