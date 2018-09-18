import * as ReactJS from 'react';
import AvatarItem from 'components/AvatarList/AvatarItem';

export interface IAvatarListProps {
  size?: 'large' | 'small' | 'mini' | 'default';
  style?: ReactJS.CSSProperties;
  children: ReactJS.ReactElement<AvatarItem> | Array<ReactJS.ReactElement<AvatarItem>>;
}

export default class AvatarList extends ReactJS.Component<IAvatarListProps, any> {
  public static Item: typeof AvatarItem;
}
