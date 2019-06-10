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
      selectedPorts: [],
      updateFiltersDisabled: true,
    };
  }

  componentDidUpdate = prevProps => {
    const { ports } = this.props;

    if (ports !== prevProps.ports) {
      Promise.resolve(
        this.onPortChange([ports[ports.findIndex(port => port.includes('all'))]])
      ).then(() => {
        this.onFilterTable();
      });
    }
  };

  onFilterTable = () => {
    const { selectedFilters, selectedPorts } = this.state;
    const { onFilterTable } = this.props;

    onFilterTable(selectedFilters, selectedPorts);
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

  onPortChange = value => {
    this.setState({ selectedPorts: value });
    this.setState({ updateFiltersDisabled: false });
  };

  onClearFilters = () => {
    const { onFilterTable } = this.props;

    this.setState(
      {
        selectedFilters: [],
        selectedPorts: [],
      },
      () => {
        const { selectedFilters } = this.state;
        onFilterTable(selectedFilters);
      }
    );
  };

  render() {
    const { filters, ports } = this.props;
    const { selectedFilters, selectedPorts, updateFiltersDisabled } = this.state;

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
          <Row style={{ display: 'flex', flexWrap: 'wrap' }}>
            <div>
              <p style={{ marginBottom: 4, fontSize: 12, fontWeight: 600 }}>hostname & port</p>
              <Select
                key="port"
                mode="multiple"
                allowClear
                placeholder="port"
                style={{ marginRight: 16, marginBottom: 16, width: 320 }}
                dropdownMatchSelectWidth={false}
                value={selectedPorts}
                onChange={this.onPortChange}
              >
                {ports.map(port => (
                  <Option key={port} value={port}>
                    {port}
                  </Option>
                ))}
              </Select>
            </div>
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
