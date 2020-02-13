import React from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Form, FormGroup, TextInput, Checkbox, ActionGroup, Button } from '@patternfly/react-core';

@connect(user => ({
  user,
}))
class Register extends React.Component {
  constructor() {
    super();
    this.state = {
      username: '',
      password: '',
      email: '',
    };
    this.handleUserNameInputChange = this.handleUserNameInputChange.bind(this);
    this.handlePassWordInputChange = this.handlePassWordInputChange.bind(this);
    this.handleEmailInputChange = this.handleEmailInputChange.bind(this);
  }

  handleUserNameInputChange = username => {
    this.setState({
      username,
    });
  };

  handlePassWordInputChange = password => {
    this.setState({
      password,
    });
  };

  handleRegisterSubmit = () => {
    const { username, password, email } = this.state;
    const { dispatch } = this.props;
    // Send the data to the backend for validation,
    // redirect to the Login page
    if (username === 'admin' && password === 'admin' && email === 'admin@admin.com') {
      dispatch(routerRedux.push('/'));
    }
  };

  handleEmailInputChange = email => {
    this.setState({
      email,
    });
  };

  render() {
    const registerForm = (
      <Form isHorizontal>
        <FormGroup
          label="Name"
          isRequired
          fieldId="horizontal-form-name"
          helperText="Please provide your username"
        >
          <TextInput
            isRequired
            type="text"
            id="horizontal-form-name"
            aria-describedby="horizontal-form-name-helper"
            name="horizontal-form-name"
            onChange={this.handleUserNameInputChange}
          />
        </FormGroup>
        <FormGroup label="Password" isRequired fieldId="horizontal-form-password">
          <TextInput
            isRequired
            type="password"
            id="horizontal-form-password"
            name="horizontal-form-password"
            onChange={this.handlePassWordInputChange}
          />
        </FormGroup>
        <FormGroup label="Email" isRequired fieldId="horizontal-form-email">
          <TextInput
            isRequired
            type="email"
            id="horizontal-form-email"
            name="horizontal-form-email"
            onChange={this.handleEmailInputChange}
          />
        </FormGroup>
        <FormGroup fieldId="remember-me">
          <Checkbox label="Remeber me" id="alt-form-checkbox-1" name="alt-form-checkbox-1" />
        </FormGroup>
        <ActionGroup>
          <Button variant="primary" onClick={() => this.handleRegisterSubmit()}>
            Register
          </Button>
          <Button variant="secondary">Cancel</Button>
        </ActionGroup>
      </Form>
    );
    return <div>{registerForm}</div>;
  }
}

export default Register;
