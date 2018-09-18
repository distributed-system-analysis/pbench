import * as ReactJS from 'react';
export interface IFooterToolbarProps {
  extra: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export default class FooterToolbar extends ReactJS.Component<IFooterToolbarProps, any> {}
