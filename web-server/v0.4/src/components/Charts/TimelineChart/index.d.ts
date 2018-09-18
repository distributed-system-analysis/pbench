import * as ReactJS from 'react';
export interface ITimelineChartProps {
  data: Array<{
    x: string;
    y1: string;
    y2: string;
  }>;
  titleMap: { y1: string; y2: string };
  padding?: [number, number, number, number];
  height?: number;
  style?: ReactJS.CSSProperties;
}

export default class TimelineChart extends ReactJS.Component<ITimelineChartProps, any> {}
