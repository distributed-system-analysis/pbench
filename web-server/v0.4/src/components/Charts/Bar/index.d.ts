import * as ReactJS from 'react';
export interface IBarProps {
  title: ReactJS.ReactNode;
  color?: string;
  padding?: [number, number, number, number];
  height: number;
  data: Array<{
    x: string;
    y: number;
  }>;
  autoLabel?: boolean;
  style?: ReactJS.CSSProperties;
}

export default class Bar extends ReactJS.Component<IBarProps, any> {}
