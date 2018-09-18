import * as ReactJS from 'react';
export interface IHeaderSearchProps {
  placeholder?: string;
  dataSource?: string[];
  onSearch?: (value: string) => void;
  onChange?: (value: string) => void;
  onPressEnter?: (value: string) => void;
  style?: ReactJS.CSSProperties;
  className?: string;
}

export default class HeaderSearch extends ReactJS.Component<IHeaderSearchProps, any> {}
