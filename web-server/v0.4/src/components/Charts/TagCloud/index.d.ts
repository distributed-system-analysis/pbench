import * as ReactJS from 'react';
export interface ITagCloudProps {
  data: Array<{
    name: string;
    value: number;
  }>;
  height: number;
  style?: ReactJS.CSSProperties;
}

export default class TagCloud extends ReactJS.Component<ITagCloudProps, any> {}
