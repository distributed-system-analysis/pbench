import React, { Component, Fragment } from 'react';
import {
  Grid,
  GridItem,
  TextContent,
  Text,
  TextVariants,
  Button,
  Dropdown,
  DropdownToggle,
} from '@patternfly/react-core';
import { CaretDownIcon } from '@patternfly/react-icons';

class PrivateRoute extends Component {
  constructor(props) {
    super(props);
    this.state = {
      isLoggedIn: false,
      isOpen: false,
      currPage: '',
    };
  }

  setLoggedIn = loggedIn => {
    this.setState({
      isLoggedIn: !loggedIn,
    });
  };

  onToggle = isOpen => {
    this.setState({
      isOpen,
    });
  };

  onSelect = () => {
    const { isOpen } = this.state;
    this.setState({
      isOpen: !isOpen,
    });
  };

  navigateToLogin = page => {
    this.setState({
      currPage: page,
    });
  };

  navigateToHome = () => {
    this.setState({
      currPage: '',
    });
  };

  render() {
    const { isLoggedIn, currPage, isOpen } = this.state;
    const { children } = this.props;
    // Basic Login methods
    const loginMethods = (
      <Grid gutter="md" style={{ padding: '10px' }}>
        <GridItem>
          <Button isBlock variant="primary" onClick={() => this.navigateToLogin('pbenchLogin')}>
            Pbench credentials
          </Button>
        </GridItem>
        <GridItem>
          <Button isBlock variant="secondary" onClick={() => this.navigateToLogin('ssoLogin')}>
            Red Hat SSO
          </Button>
        </GridItem>
        <GridItem>
          <Button isBlock variant="secondary" onClick={() => this.navigateToLogin('githubLogin')}>
            GitHub
          </Button>
        </GridItem>
      </Grid>
    );
    // Action handlers for register and forgot password
    const restLoginHandlers = (
      <Grid
        gutter="md"
        style={{ borderTop: '2px solid black', padding: '10px', textAlign: 'center' }}
      >
        <GridItem>
          <TextContent style={{ padding: '10px' }}>
            <Text component={TextVariants.h2}>
              Need an account?
              <Button variant="link">
                <u>Sign up.</u>
              </Button>
            </Text>
            <Text component={TextVariants.h2}>
              <Button variant="link">
                <u>Forgot username or password?</u>
              </Button>
            </Text>
          </TextContent>
        </GridItem>
      </Grid>
    );

    // DropdownMenu items
    const dropdownItems = [];

    if (isLoggedIn) {
      return <Fragment>{children}</Fragment>;
    }
    return (
      <Grid style={{ marginTop: '200px' }}>
        <GridItem
          sm={8}
          md={4}
          lg={4}
          smOffset={2}
          mdOffset={2}
          lgOffset={2}
          style={{ border: '2px solid black' }}
        >
          <TextContent style={{ padding: '10px' }}>
            <Text component={TextVariants.h2}>
              Login with...
              <Dropdown
                style={{ float: 'right' }}
                onSelect={this.onSelect}
                toggle={
                  <DropdownToggle
                    id="toggle-id"
                    onToggle={this.onToggle}
                    iconComponent={CaretDownIcon}
                  >
                    English
                  </DropdownToggle>
                }
                isOpen={isOpen}
                dropdownItems={dropdownItems}
              />
            </Text>
          </TextContent>
          {currPage === 'register' ? (
            <Fragment>Register</Fragment>
          ) : (
            <Fragment>
              {!currPage ? loginMethods : <Fragment>Login</Fragment>}
              {restLoginHandlers}
            </Fragment>
          )}
        </GridItem>
        <GridItem sm={8} md={4} lg={4}>
          abcd
        </GridItem>
      </Grid>
    );
  }
}

export default PrivateRoute;
