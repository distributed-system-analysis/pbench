import * as ReactJS from 'react';
export interface INumberInfoProps {
  title?: ReactJS.ReactNode | string;
  subTitle?: ReactJS.ReactNode | string;
  total?: ReactJS.ReactNode | string;
  status?: 'up' | 'down';
  theme?: string;
  gap?: number;
  subTotal?: number;
  style?: ReactJS.CSSProperties;
}

export default class NumberInfo extends ReactJS.Component<INumberInfoProps, any> {}
