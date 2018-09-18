import * as ReactJS from 'react';
export interface ICountDownProps {
  format?: (time: number) => void;
  target: Date | number;
  onEnd?: () => void;
  style?: ReactJS.CSSProperties;
}

export default class CountDown extends ReactJS.Component<ICountDownProps, any> {}
