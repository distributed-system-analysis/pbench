import React from 'react';
import { Table as AntdTable } from 'antd';

const Table = props => {
  const { dataSource, columns, loading, onRow, ...childProps } = props;

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
};

export default Table;
