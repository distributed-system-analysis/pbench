import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Table as AntdTable } from 'antd';

export default class Table extends Component {
  static propTypes = {
    columns: PropTypes.array,
    dataSource: PropTypes.array,
    loading: PropTypes.bool,
    onRow: PropTypes.func,
  };

  static defaultProps = {
    columns: [],
    dataSource: [],
    loading: false,
    onRow: () => {},
  };

  render() {
    const { dataSource, columns, loading, onRow, ...childProps } = this.props;

    return (
      <AntdTable
        bordered
        bodyStyle={{ borderRadius: 4 }}
        columns={columns}
        dataSource={dataSource}
        loading={loading}
        onRow={onRow}
        scroll={{
          x: true,
        }}
        {...childProps}
      />
    );
  }
}
