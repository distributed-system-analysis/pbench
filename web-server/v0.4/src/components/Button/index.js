import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Button as AntdButton } from 'antd';

export default class Button extends Component {
  static propTypes = {
    name: PropTypes.string.isRequired,
    type: PropTypes.string,
    disabled: PropTypes.bool,
    onClick: PropTypes.func.isRequired,
  };

  static defaultProps = {
    type: 'primary',
    disabled: false,
  };

  render() {
    const { name, type, disabled, onClick, ...props } = this.props;

    return (
      <AntdButton type={type} disabled={disabled} onClick={onClick} {...props}>
        {name}
      </AntdButton>
    );
  }
}
