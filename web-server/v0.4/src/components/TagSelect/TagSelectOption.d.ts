import * as ReactJS from 'react';

export interface ITagSelectOptionProps {
  value: string | number;
  style?: ReactJS.CSSProperties;
}

export default class TagSelectOption extends ReactJS.Component<ITagSelectOptionProps, any> {}
