import React from 'react';
import { Grid, GridItem, TextContent, Text, TextVariants, Button } from '@patternfly/react-core';

class PrivateRoute extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      isLoggedIn: false,
    };
  }

  setLoggedIn = a => {
    this.setState({
      isLoggedIn: !a,
    });
  };

  render() {
    const { isLoggedIn } = this.state;
    const { children } = this.props;
    // Basic Login methods
    const loginMethods = (
      <Grid gutter="md" style={{ padding: '10px' }}>
        <GridItem>
          <Button isBlock variant="primary">
            Pbench credentials
          </Button>
        </GridItem>
        <GridItem>
          <Button isBlock variant="secondary">
            Red Hat SSO
          </Button>
        </GridItem>
        <GridItem>
          <Button isBlock variant="secondary">
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
    if (isLoggedIn) {
      return <div>{children}</div>;
    }
    return (
      <Grid>
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
            <Text component={TextVariants.h2}>Login with...</Text>
          </TextContent>
          {loginMethods}
          {restLoginHandlers}
        </GridItem>
        <GridItem sm={8} md={4} lg={4}>
          abcd
        </GridItem>
      </Grid>
    );
  }
}

export default PrivateRoute;
