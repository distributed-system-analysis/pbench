import * as ReactJS from 'react';
export interface IRadarProps {
  title?: ReactJS.ReactNode;
  height: number;
  padding?: [number, number, number, number];
  hasLegend?: boolean;
  data: Array<{
    name: string;
    label: string;
    value: string;
  }>;
  style?: ReactJS.CSSProperties;
}

export default class Radar extends ReactJS.Component<IRadarProps, any> {}
