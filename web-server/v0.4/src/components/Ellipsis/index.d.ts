import * as ReactJS from 'react';
export interface IEllipsisProps {
  tooltip?: boolean;
  length?: number;
  lines?: number;
  style?: ReactJS.CSSProperties;
  className?: string;
  fullWidthRecognition?: boolean;
}

export default class Ellipsis extends ReactJS.Component<IEllipsisProps, any> {}
