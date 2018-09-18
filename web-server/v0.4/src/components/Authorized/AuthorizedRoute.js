import ReactJS from 'react';
import { Route, Redirect } from 'react-router-dom';
import Authorized from 'components/Authorized/Authorized';

class AuthorizedRoute extends ReactJS.Component {
  render() {
    const { component: Component, render, authority, redirectPath, ...rest } = this.props;
    return (
      <Authorized
        authority={authority}
        noMatch={<Route {...rest} render={() => <Redirect to={{ pathname: redirectPath }} />} />}
      >
        <Route {...rest} render={props => (Component ? <Component {...props} /> : render(props))} />
      </Authorized>
    );
  }
}

export default AuthorizedRoute;
