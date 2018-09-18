import * as ReactJS from 'react';
export interface IFieldProps {
  label: ReactJS.ReactNode;
  value: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export default class Field extends ReactJS.Component<IFieldProps, any> {}
