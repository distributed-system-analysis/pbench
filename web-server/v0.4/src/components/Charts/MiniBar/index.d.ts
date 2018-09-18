import * as ReactJS from 'react';
export interface IMiniBarProps {
  color?: string;
  height: number;
  data: Array<{
    x: number | string;
    y: number;
  }>;
  style?: ReactJS.CSSProperties;
}

export default class MiniBar extends ReactJS.Component<IMiniBarProps, any> {}
