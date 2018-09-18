import ReactJS from 'react';
import CheckPermissions from 'components/Authorized/CheckPermissions';

class Authorized extends ReactJS.Component {
  render() {
    const { children, authority, noMatch = null } = this.props;
    const childrenRender = typeof children === 'undefined' ? null : children;
    return CheckPermissions(authority, childrenRender, noMatch);
  }
}

export default Authorized;
