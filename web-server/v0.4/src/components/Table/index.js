import React from 'react';
import { Table as AntdTable } from 'antd';
import constants from '../../../config/constants';

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
      pagination={{
        defaultPageSize: 10,
        showSizeChanger: true,
        pageSizeOptions: constants.tableSizeOptions,
      }}
      {...childProps}
    />
  );
};

export default Table;
