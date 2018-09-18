import * as ReactJS from 'react';
export interface IGaugeProps {
  title: ReactJS.ReactNode;
  color?: string;
  height: number;
  bgColor?: number;
  percent: number;
  style?: ReactJS.CSSProperties;
}

export default class Gauge extends ReactJS.Component<IGaugeProps, any> {}
