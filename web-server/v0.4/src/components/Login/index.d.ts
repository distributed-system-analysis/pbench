import * as ReactJS from 'react';
import Button from 'antd/lib/button';
export interface LoginProps {
  defaultActiveKey?: string;
  onTabChange?: (key: string) => void;
  style?: ReactJS.CSSProperties;
  onSubmit?: (error: any, values: any) => void;
}

export interface TabProps {
  key?: string;
  tab?: ReactJS.ReactNode;
}
export class Tab extends ReactJS.Component<TabProps, any> {}

export interface LoginItemProps {
  name?: string;
  rules?: any[];
  style?: ReactJS.CSSProperties;
  onGetCaptcha?: () => void;
  placeholder?: string;
}

export class LoginItem extends ReactJS.Component<LoginItemProps, any> {}

export default class Login extends ReactJS.Component<LoginProps, any> {
  static Tab: typeof Tab;
  static UserName: typeof LoginItem;
  static Password: typeof LoginItem;
  static Mobile: typeof LoginItem;
  static Captcha: typeof LoginItem;
  static Submit: typeof Button;
}
