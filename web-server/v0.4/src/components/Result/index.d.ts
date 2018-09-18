import * as ReactJS from 'react';
export interface IResultProps {
  type: 'success' | 'error';
  title: ReactJS.ReactNode;
  description?: ReactJS.ReactNode;
  extra?: ReactJS.ReactNode;
  actions?: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export default class Result extends ReactJS.Component<IResultProps, any> {}
