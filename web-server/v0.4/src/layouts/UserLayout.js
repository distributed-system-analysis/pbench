import ReactJS from 'react';
import { Link, Redirect, Switch, Route } from 'dva/router';
import DocumentTitle from 'react-document-title';
import styles from './UserLayout.less';
import logo from '../assets/rh_logo.png';
import { getRoutes, getPageQuery, getQueryPath } from '../utils/utils';

function getLoginPathWithRedirectPath() {
  const params = getPageQuery();
  const { redirect } = params;
  return getQueryPath('/user/login', {
    redirect,
  });
}

class UserLayout extends ReactJS.PureComponent {
  getPageTitle() {
    const { routerData, location } = this.props;
    const { pathname } = location;
    let title = 'Pbench Dashboard';
    if (routerData[pathname] && routerData[pathname].name) {
      title = `${routerData[pathname].name} - Pbench Dashboard`;
    }
    return title;
  }

  render() {
    const { routerData, match } = this.props;
    return (
      <DocumentTitle title={this.getPageTitle()}>
        <div className={styles.container}>
          <div className={styles.content}>
            <div className={styles.top}>
              <div className={styles.header}>
                <Link to="/">
                  <img alt="logo" className={styles.logo} src={logo} />
                </Link>
              </div>
            </div>
            {this.props.children}
          </div>
        </div>
      </DocumentTitle>
    );
  }
}

export default UserLayout;
