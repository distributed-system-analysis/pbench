import * as ReactJS from 'react';
export interface IGlobalFooterProps {
  links?: Array<{
    key?: string;
    title: ReactJS.ReactNode;
    href: string;
    blankTarget?: boolean;
  }>;
  copyright?: ReactJS.ReactNode;
  style?: ReactJS.CSSProperties;
}

export default class GlobalFooter extends ReactJS.Component<IGlobalFooterProps, any> {}
