import React from 'react';
import { Link } from 'dva/router';
import DocumentTitle from 'react-document-title';
import styles from './UserLayout.less';
import logo from '../assets/pbench_logo.png';

class UserLayout extends React.PureComponent {
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
    const { children } = this.props;

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
            {children}
          </div>
        </div>
      </DocumentTitle>
    );
  }
}

export default UserLayout;
