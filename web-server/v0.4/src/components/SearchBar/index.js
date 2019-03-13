import React, { PureComponent } from 'react';
import PropTypes from 'prop-types';
import { Input, Icon } from 'antd';

const { Search } = Input;

export default class SearchBar extends PureComponent {
  static propTypes = {
    onSearch: PropTypes.func.isRequired,
    style: PropTypes.object,
  };

  static defaultProps = {
    style: {},
  };

  constructor(props) {
    super(props);

    this.state = {
      searchValue: '',
    };
  }

  onChange = e => {
    this.setState({ searchValue: e.target.value });
  };

  emitEmpty = () => {
    const { onSearch } = this.props;

    this.searchBar.focus();
    onSearch('');
    this.setState({ searchValue: '' });
  };

  render() {
    const { onSearch, placeholder, style } = this.props;
    const { searchValue } = this.state;
    const suffix = searchValue ? <Icon type="close-circle" onClick={this.emitEmpty} /> : <span />;

    return (
      <div style={{ display: 'flex', flexDirection: 'row', alignContent: 'center', maxWidth: 300, ...style }}>
        <Search
          ref={node => {
            this.searchBar = node;
            return this.searchBar;
          }}
          prefix={<Icon type="search" style={{ color: 'rgba(0,0,0,.25)' }} />}
          suffix={suffix}
          placeholder={placeholder}
          value={searchValue}
          onChange={this.onChange}
          onSearch={value => onSearch(value)}
          enterButton="Search"
        />
      </div>
    );
  }
}
