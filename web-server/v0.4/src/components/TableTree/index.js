import React, { PureComponent } from 'react';
import PropTypes from 'prop-types';
import { Table } from 'antd';

export default class TableTree extends PureComponent {
  static propTypes = {
    id: PropTypes.string,
    dataSource: PropTypes.array,
    extension: PropTypes.array,
    onload: PropTypes.func,
    config: PropTypes.object,
  };

  static defaultProps = {
    id: '',
    dataSource: [],
    extension: [],
    onload: () => {},
    config: {},
  };

  constructor(props) {
    super(props);
    this.fileData = [];
    this.state = {
      expandedKeys: [],
    };
  }

  componentDidMount() {
    const { dataSource, onload } = this.props;
    onload(dataSource);
  }

  onExpand = (expanded, record) => {
    let { expandedKeys } = this.state;
    const keys = expandedKeys;
    expandedKeys = expanded ? keys.concat(record.key) : keys.slice(0, keys.indexOf(record.key));
    this.setState({ expandedKeys });
  };

  filterNames = (record, value) =>
    record.some(childRecord => {
      if (childRecord.name.toLowerCase().includes(value)) {
        return true;
      }
      if (childRecord.children) {
        return this.filterNames(childRecord.children, value);
      }
      return false;
    });

  render() {
    const { id, dataSource, extension, config } = this.props;
    const extensions = extension.map(x => ({ text: x, value: x }));
    const { expandedKeys } = this.state;
    const configLink = `${config.config + config.controller_name}/${config.run_name}/`;

    const columns = [
      {
        title: 'Names',
        dataIndex: 'name',
        key: 'name',
        width: '60%',
        filters: extensions,
        render: (text, record) => {
          if (record.url === '') {
            return text;
          }
          return (
            <a
              style={{ color: 'inherit' }}
              href={configLink + record.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {text}
            </a>
          );
        },
        onFilter: (value, record) =>
          (record.children && this.filterNames(record.children, value)) ||
          record.name.toLowerCase().includes(value),
      },
      {
        title: 'Size',
        dataIndex: 'size',
        key: 'size',
        width: '20%',
      },
      {
        title: 'Mode',
        dataIndex: 'mode',
        key: 'mode',
      },
    ];

    return (
      <div>
        <Table
          id={id}
          columns={columns}
          dataSource={dataSource}
          rowKey={tocTree => tocTree.key}
          onExpand={this.onExpand}
          expandedRowKeys={expandedKeys}
        />
      </div>
    );
  }
}
