import * as ReactJS from 'react';
export interface IWaterWaveProps {
  title: ReactJS.ReactNode;
  color?: string;
  height: number;
  percent: number;
  style?: ReactJS.CSSProperties;
}

export default class WaterWave extends ReactJS.Component<IWaterWaveProps, any> {}
