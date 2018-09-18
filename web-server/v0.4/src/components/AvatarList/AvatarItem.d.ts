import * as ReactJS from 'react';
export interface IAvatarItemProps {
  tips: ReactJS.ReactNode;
  src: string;
  style?: ReactJS.CSSProperties;
}

export default class AvatarItem extends ReactJS.Component<IAvatarItemProps, any> {
  constructor(props: IAvatarItemProps);
}
