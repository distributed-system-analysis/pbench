import React from 'react';
import PropTypes from 'prop-types';
import { Layout, Icon, Spin, message } from 'antd';
import DocumentTitle from 'react-document-title';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { PersistGate } from 'redux-persist/integration/react';
import { persistStore } from 'redux-persist';
import { ContainerQuery } from 'react-container-query';
import classNames from 'classnames';
import pathToRegexp from 'path-to-regexp';
import { enquireScreen, unenquireScreen } from 'enquire-js';
import memoizeOne from 'memoize-one';
import deepEqual from 'lodash/isEqual';
import GlobalFooter from 'ant-design-pro/lib/GlobalFooter';
import GlobalHeader from '@/components/GlobalHeader';
import SiderMenu from '../components/SiderMenu';
import Authorized from '../utils/Authorized';
import getMenuData from '../common/menu';
import logo from '../assets/pbench_logo.png';

const { Content, Header, Footer } = Layout;
const { check } = Authorized;

const redirectData = [];
const getRedirect = item => {
  if (item && item.children) {
    if (item.children[0] && item.children[0].path) {
      redirectData.push({
        from: `${item.path}`,
        to: `${item.children[0].path}`,
      });
      item.children.forEach(children => {
        getRedirect(children);
      });
    }
  }
};
getMenuData().forEach(getRedirect);

const getBreadcrumbNameMap = memoizeOne(menu => {
  const routerMap = {};
  const mergeMeunAndRouter = menuData => {
    menuData.forEach(menuItem => {
      if (menuItem.children) {
        mergeMeunAndRouter(menuItem.children);
      }
      // Reduce memory usage
      routerMap[menuItem.path] = menuItem;
    });
  };
  mergeMeunAndRouter(menu);
  return routerMap;
}, deepEqual);

const query = {
  'screen-xs': {
    maxWidth: 575,
  },
  'screen-sm': {
    minWidth: 576,
    maxWidth: 767,
  },
  'screen-md': {
    minWidth: 768,
    maxWidth: 991,
  },
  'screen-lg': {
    minWidth: 992,
    maxWidth: 1199,
  },
  'screen-xl': {
    minWidth: 1200,
    maxWidth: 1599,
  },
  'screen-xxl': {
    minWidth: 1600,
  },
};

let isMobile;
enquireScreen(b => {
  isMobile = b;
});

@connect(({ global, datastore, loading }) => ({
  datastoreConfig: datastore.datastoreConfig,
  collapsed: global.collapsed,
  sessionBannerVisible: global.sessionBannerVisible,
  sessionDescription: global.sessionDescription,
  sessionId: global.sessionId,
  savingSession: loading.effects['global/saveUserSession'],
}))
class BasicLayout extends React.PureComponent {
  static childContextTypes = {
    location: PropTypes.object,
    breadcrumbNameMap: PropTypes.object,
  };

  state = {
    isMobile,
  };

  constructor(props) {
    super(props);
    this.getPageTitle = memoizeOne(this.getPageTitle);
    this.breadcrumbNameMap = getBreadcrumbNameMap(getMenuData());
    // eslint-disable-next-line no-underscore-dangle
    this.persistor = persistStore(window.g_app._store);
  }

  getChildContext() {
    const { location } = this.props;
    return {
      location,
      breadcrumbNameMap: this.breadcrumbNameMap,
    };
  }

  componentDidMount() {
    this.enquireHandler = enquireScreen(mobile => {
      this.setState({
        isMobile: mobile,
      });
    });
  }

  componentWillUnmount() {
    unenquireScreen(this.enquireHandler);
  }

  getPageTitle = pathname => {
    let currRouterData = null;
    // match params path
    Object.keys(this.breadcrumbNameMap).forEach(key => {
      if (pathToRegexp(key).test(pathname)) {
        currRouterData = this.breadcrumbNameMap[key];
      }
    });
    if (!currRouterData) {
      return 'Pbench Dashboard';
    }
    return `${currRouterData.name} - Pbench Dashboard`;
  };

  getBaseRedirect = () => {
    // According to the url parameter to redirect
    const urlParams = new URL(window.location.href);

    const redirect = urlParams.searchParams.get('redirect');
    // Remove the parameters in the url
    if (redirect) {
      urlParams.searchParams.delete('redirect');
      window.history.replaceState(null, 'redirect', urlParams.href);
    } else {
      const { routerData } = this.props;
      // get the first authorized route path in routerData
      const authorizedPath = Object.keys(routerData).find(
        item => check(routerData[item].authority, item) && item !== '/'
      );
      return authorizedPath;
    }
    return redirect;
  };

  handleMenuCollapse = collapsed => {
    const { dispatch } = this.props;
    dispatch({
      type: 'global/changeLayoutCollapsed',
      payload: collapsed,
    });
  };

  handleNoticeClear = type => {
    message.success(`${type}`);
    const { dispatch } = this.props;
    dispatch({
      type: 'global/clearNotices',
      payload: type,
    });
  };

  handleMenuClick = ({ key }) => {
    const { dispatch } = this.props;
    if (key === 'triggerError') {
      dispatch(routerRedux.push('/exception/trigger'));
      return;
    }
    if (key === 'logout') {
      dispatch({
        type: 'login/logout',
      });
    }
  };

  handleNoticeVisibleChange = visible => {
    const { dispatch } = this.props;
    if (visible) {
      dispatch({
        type: 'global/fetchNotices',
      });
    }
  };

  render() {
    const {
      datastoreConfig,
      collapsed,
      savingSession,
      sessionBannerVisible,
      sessionDescription,
      sessionId,
      fetchingNotices,
      children,
      location: { pathname },
    } = this.props;
    const { isMobile: mb } = this.state;
    // const baseRedirect = this.getBaseRedirect();
    const layout = (
      <Layout>
        <SiderMenu
          logo={logo}
          // If you do not have the Authorized parameter
          // you will be forced to jump to the 403 interface without permission
          Authorized={Authorized}
          menuData={getMenuData()}
          collapsed={collapsed}
          // eslint-disable-next-line no-restricted-globals
          location={location}
          isMobile={mb}
          onCollapse={this.handleMenuCollapse}
        />
        <Layout>
          <Header style={{ padding: 0 }}>
            <GlobalHeader
              logo={logo}
              fetchingNotices={fetchingNotices}
              collapsed={collapsed !== true}
              datastoreConfig={datastoreConfig}
              savingSession={savingSession}
              sessionBannerVisible={sessionBannerVisible}
              sessionDescription={sessionDescription}
              sessionId={sessionId}
              isMobile={mb}
              onNoticeClear={this.handleNoticeClear}
              onCollapse={this.handleMenuCollapse}
              onMenuClick={this.handleMenuClick}
              onNoticeVisibleChange={this.handleNoticeVisibleChange}
            />
          </Header>
          <Content
            style={{
              margin: sessionBannerVisible ? '104px 24px 0' : '24px 24px 0',
              height: '100%',
            }}
          >
            <PersistGate
              persistor={this.persistor}
              loading={
                <Spin
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                  spinning
                />
              }
            >
              {children}
            </PersistGate>
          </Content>
          <Footer style={{ padding: 0 }}>
            <GlobalFooter
              links={[
                {
                  key: 'Pbench Dashboard',
                  title: 'Pbench Dashboard',
                  href: 'https://example.com',
                  blankTarget: true,
                },
                {
                  key: 'github',
                  title: <Icon type="github" />,
                  href: 'https://example.com',
                  blankTarget: true,
                },
                {
                  key: 'PBench',
                  title: 'PBench',
                  href: 'http://example.com/',
                  blankTarget: true,
                },
              ]}
            />
          </Footer>
        </Layout>
      </Layout>
    );

    return (
      <DocumentTitle title={this.getPageTitle(pathname)}>
        <ContainerQuery query={query}>
          {params => <div className={classNames(params)}>{layout}</div>}
        </ContainerQuery>
      </DocumentTitle>
    );
  }
}

export default BasicLayout;
