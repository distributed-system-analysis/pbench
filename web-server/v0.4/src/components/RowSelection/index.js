import React, { PureComponent } from 'react';
import PropTypes from 'prop-types';

import Button from '../Button';

export default class RowSelection extends PureComponent {
  static propTypes = {
    selectedItems: PropTypes.array.isRequired,
    compareActionName: PropTypes.string.isRequired,
    onCompare: PropTypes.func.isRequired,
    styles: PropTypes.object,
  };

  static defaultProps = {
    styles: {},
  } 

  render () {
    const { selectedItems, compareActionName, onCompare, styles } = this.props;
    const selectedItemsLength = selectedItems.length;

    return (
      <div styles={styles}>
        <Button
          type="primary"
          onClick={onCompare}
          name={compareActionName}
          disabled={!(selectedItemsLength > 0)}
        />
        <span style={{ marginLeft: 8 }}>
          {selectedItemsLength > 0 ? `Selected ${selectedItemsLength} items` : ''}
        </span>
      </div>
    );
  }
}
