import React, { Component, Fragment } from 'react';
import { Form, FormGroup, TextInput, Checkbox, ActionGroup, Button } from '@patternfly/react-core';

class PbenchLoginHandler extends Component {
  constructor(props) {
    super(props);
    this.state = {
      username: '',
      password: '',
    };
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
    // validate from the backend
    const { username, password } = this.state;
    const { setLoggedIn } = this.props;
    if (username === 'admin' && password === 'admin') {
      setLoggedIn(true);
    } else {
      console.log('Wrong username/password pair');
    }
  };

  render() {
    const form = (
      <Form style={{ padding: '10px' }}>
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
        <FormGroup fieldId="remember-me">
          <Checkbox label="Remeber me" id="alt-form-checkbox-1" name="alt-form-checkbox-1" />
        </FormGroup>
        <ActionGroup>
          <Button isBlock variant="primary" onClick={() => this.handleLoginSubmit()}>
            Submit
          </Button>
        </ActionGroup>
      </Form>
    );
    return <Fragment>{form}</Fragment>;
  }
}

export const SsoLoginHandler = () => {
  return <Fragment>Redirecting to Redhat Kerberos...</Fragment>;
};

export const GithubLoginHandler = () => {
  return <Fragment>Redirecting to Github...</Fragment>;
};

export default props => {
  switch (props.pageToRender) {
    case 'pbenchLogin':
      return <PbenchLoginHandler setLoggedIn={props.setLoggedIn} />;
    case 'ssoLogin':
      return <SsoLoginHandler />;
    case 'githubLogin':
      return <GithubLoginHandler />;
    default:
      return <Fragment>Go back</Fragment>;
  }
};
