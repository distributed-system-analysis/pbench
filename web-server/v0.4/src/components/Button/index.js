import React from 'react';
import { Button as AntdButton } from 'antd';

const Button = props => {
  const { name, type, disabled, onClick } = props;

  return (
    <AntdButton type={type} disabled={disabled} onClick={onClick} {...props}>
      {name}
    </AntdButton>
  );
};

export default Button;
