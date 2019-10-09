import React, { PureComponent } from 'react';
import PropTypes from 'prop-types';
import { Select, Form } from 'antd';

import Button from '../Button';

const FormItem = Form.Item;

export default class MonthSelect extends PureComponent {
  static propTypes = {
    indices: PropTypes.array,
    value: PropTypes.array,
    onChange: PropTypes.func,
    reFetch: PropTypes.func,
    updateButtonVisible: PropTypes.bool,
  };

  static defaultProps = {
    indices: [],
    value: ['0'],
    onChange: () => {},
    reFetch: () => {},
    updateButtonVisible: true,
  };

  constructor(props) {
    super(props);

    this.state = {
      updateDisabled: true,
    };
  }

  reFetch = () => {
    const { reFetch } = this.props;
    reFetch();
    this.setState({ updateDisabled: true });
  };

  onUpdateMonth = selectedValues => {
    const { indices, onChange } = this.props;

    if (selectedValues.length === 0) {
      onChange([indices[0]]);
    } else {
      onChange(selectedValues);
      this.setState({ updateDisabled: false });
    }
  };

  render() {
    const { indices, value, updateButtonVisible } = this.props;
    const { updateDisabled } = this.state;

    return (
      <div>
        <FormItem>
          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder="Select index"
            value={value}
            onChange={selectedValues => this.onUpdateMonth(selectedValues)}
            tokenSeparators={[',']}
          >
            {indices.map(item => (
              <Select.Option key={item}>{item}</Select.Option>
            ))}
          </Select>
        </FormItem>
        {updateButtonVisible ? (
          <FormItem>
            <Button name="Update" type="primary" disabled={updateDisabled} onClick={this.reFetch}>
              Update
            </Button>
          </FormItem>
        ) : (
          <div />
        )}
      </div>
    );
  }
}
