import * as ReactJS from 'react';
export interface IMiniProgressProps {
  target: number;
  color?: string;
  strokeWidth?: number;
  percent?: number;
  style?: ReactJS.CSSProperties;
}

export default class MiniProgress extends ReactJS.Component<IMiniProgressProps, any> {}
