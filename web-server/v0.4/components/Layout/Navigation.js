import React from 'react';
import Link from '../Link';
import history from '../../core/history';
import PfBreakpoints from './PfBreakpoints';
import PfVerticalNavigation from './PfVerticalNavigation';

class Navigation extends React.Component {

  componentDidMount() {
    // Initialize the vertical navigation
    $().setupVerticalNavigation(true);
  }

  render() {
    let location = history.getCurrentLocation();
    let homeRoutes = ['/', '/home', '/stages'];
    return (
      <div className="nav-pf-vertical">
        <ul className="list-group">
          <li className={"list-group-item" + (location.pathname == '/' ? ' active' : '')}>
            <Link to="/">
              <span className="fa fa-dashboard" data-toggle="tooltip" title="Controllers"></span>
              <span className="list-group-item-value">Controllers</span>
            </Link>
          </li>
          {/*}<li className={"list-group-item" + (location.pathname == '/environments' ? ' active' : '')}>
            <Link to="/environments">
              <span className="fa fa-paper-plane" data-toggle="tooltip" title="Amet"></span>
              <span className="list-group-item-value">Environments</span>
            </Link>
          </li>*/}
        </ul>
      </div>
    );
  }

}

export default Navigation;
