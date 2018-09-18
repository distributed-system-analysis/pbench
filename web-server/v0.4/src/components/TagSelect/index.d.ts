import * as ReactJS from 'react';
import TagSelectOption from 'components/TagSelect/TagSelectOption';

export interface ITagSelectProps {
  onChange?: (value: string[]) => void;
  expandable?: boolean;
  value?: string[] | number[];
  style?: ReactJS.CSSProperties;
}

export default class TagSelect extends ReactJS.Component<ITagSelectProps, any> {
  public static Option: typeof TagSelectOption;
  private children:
    | ReactJS.ReactElement<TagSelectOption>
    | Array<ReactJS.ReactElement<TagSelectOption>>;
}
