import * as ReactJS from 'react';
export interface IExceptionProps {
  type?: '403' | '404' | '500';
  title?: ReactJS.ReactNode;
  desc?: ReactJS.ReactNode;
  img?: string;
  actions?: ReactJS.ReactNode;
  linkElement?: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export default class Exception extends ReactJS.Component<IExceptionProps, any> {}
