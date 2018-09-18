import * as ReactJS from 'react';

export interface ITrendProps {
  colorful?: boolean;
  flag: 'up' | 'down';
  style?: ReactJS.CSSProperties;
  reverseColor?: boolean;
}

export default class Trend extends ReactJS.Component<ITrendProps, any> {}
