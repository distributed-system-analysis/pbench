import * as ReactJS from 'react';
import Description from 'components/DescriptionList/Description';

export interface IDescriptionListProps {
  layout?: 'horizontal' | 'vertical';
  col?: number;
  title: ReactJS.ReactNode;
  gutter?: number;
  size?: 'large' | 'small';
  style?: ReactJS.CSSProperties;
}

export default class DescriptionList extends ReactJS.Component<IDescriptionListProps, any> {
  public static Description: typeof Description;
}
