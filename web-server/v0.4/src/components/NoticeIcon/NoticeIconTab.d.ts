import * as ReactJS from 'react';
export interface INoticeIconData {
  avatar?: string;
  title?: ReactJS.ReactNode;
  description?: ReactJS.ReactNode;
  datetime?: ReactJS.ReactNode;
  extra?: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export interface INoticeIconTabProps {
  list?: INoticeIconData[];
  title?: string;
  emptyText?: ReactJS.ReactNode;
  emptyImage?: string;
  style?: ReactJS.CSSProperties;
}

export default class NoticeIconTab extends ReactJS.Component<INoticeIconTabProps, any> {}
