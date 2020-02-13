import React from 'react';
import { routerRedux } from 'dva/router';
import { connect } from 'dva';
import { Form, FormGroup, TextInput, Checkbox, ActionGroup, Button } from '@patternfly/react-core';

@connect(user => ({
  user,
}))
class Login extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      username: '',
      password: '',
    };
    this.handleUserNameInputChange = this.handleUserNameInputChange.bind(this);
    this.handlePassWordInputChange = this.handlePassWordInputChange.bind(this);
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

  handleLoginSubmit = () => {
    const { username, password } = this.state;
    const { setLoggedIn } = this.props;
    // Send the data to the backend for validation,
    // if no err, store in the local storage
    if (username === 'admin' && password === 'admin') {
      setLoggedIn(true);
    } else console.log('wrong username/password pair');
  };

  showRegisterPage = () => {
    const { dispatch } = this.props;
    dispatch(routerRedux.push('/register'));
  };

  render() {
    const { username, password } = this.state;
    const form = (
      <Form isHorizontal>
        <FormGroup
          label="Name"
          isRequired
          fieldId="horizontal-form-name"
          helperText="Please provide your username"
        >
          <TextInput
            isRequired
            value={username}
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
            value={password}
            type="password"
            id="horizontal-form-password"
            name="horizontal-form-password"
            onChange={this.handlePassWordInputChange}
          />
        </FormGroup>
        <FormGroup fieldId="remember-me">
          <Checkbox label="Remeber me" id="alt-form-checkbox-1" name="alt-form-checkbox-1" />
        </FormGroup>
        <ActionGroup>
          <Button variant="primary" onClick={() => this.handleLoginSubmit()}>
            Login
          </Button>
          <Button variant="secondary" onClick={() => this.showRegisterPage()}>
            Register
          </Button>
        </ActionGroup>
      </Form>
    );
    return <div>{form}</div>;
  }
}

export default Login;
