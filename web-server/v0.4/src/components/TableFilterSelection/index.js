import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Form, Row, Select } from 'antd';

import Button from '../Button';

const { Option } = Select;

export default class TableFilterSelection extends Component {
  static propTypes = {
    onFilterTable: PropTypes.func.isRequired,
    filters: PropTypes.object.isRequired,
  };

  constructor(props) {
    super(props);

    this.state = {
      selectedFilters: {},
      updateFiltersDisabled: true,
    };
  }

  onFilterTable = () => {
    const { selectedFilters } = this.state;
    const { onFilterTable } = this.props;

    onFilterTable(selectedFilters);
    this.setState({ updateFiltersDisabled: true });
  };

  onFilterChange = (value, category) => {
    const { selectedFilters } = this.state;

    if (value) {
      selectedFilters[category] = value;
    } else {
      delete selectedFilters[category];
    }

    this.setState({ selectedFilters });
    this.setState({ updateFiltersDisabled: false });
  };

  onClearFilters = () => {
    this.setState({
      selectedFilters: [],
    });
    this.setState({ updateFiltersDisabled: false });
  };

  render() {
    const { filters } = this.props;
    const { selectedFilters, updateFiltersDisabled } = this.state;

    return (
      <div>
        <Form
          style={{
            padding: '24px',
            backgroundColor: '#FAFAFA',
            border: '1px solid #D9D9D9',
            borderRadius: '6px',
          }}
        >
          <Row style={{ display: 'flex', flexWrap: 'wrap' }}>
            {Object.keys(filters).map(category => (
              <div key={category}>
                <p style={{ marginBottom: 4, fontSize: 12, fontWeight: 600 }}>{category}</p>
                <Select
                  key={category}
                  allowClear
                  placeholder={category}
                  style={{ marginRight: 16, marginBottom: 16, width: 160 }}
                  dropdownMatchSelectWidth={false}
                  value={selectedFilters[category]}
                  onChange={value => this.onFilterChange(value, category)}
                >
                  {filters[category].map(categoryData => (
                    <Option key={categoryData} value={categoryData}>
                      {categoryData}
                    </Option>
                  ))}
                </Select>
              </div>
            ))}
          </Row>
          <Row>
            <div style={{ textAlign: 'right' }}>
              <Button
                type="primary"
                htmlType="submit"
                name="Filter"
                disabled={updateFiltersDisabled}
                onClick={this.onFilterTable}
              />
              <Button
                type="secondary"
                style={{ marginLeft: 8 }}
                onClick={this.onClearFilters}
                name="Clear"
              />
            </div>
          </Row>
        </Form>
      </div>
    );
  }
}
