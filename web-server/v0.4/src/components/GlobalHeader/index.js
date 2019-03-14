import { PureComponent } from 'react';
import { routerRedux } from 'dva/router';
import { Icon, Divider, Tooltip, Alert, Badge } from 'antd';
import Debounce from 'lodash-decorators/debounce';
import { connect } from 'dva';
import styles from './index.less';
import SessionModal from '../SessionModal';

@connect(store => ({
  store,
}))
class GlobalHeader extends PureComponent {
  componentWillUnmount() {
    this.triggerResizeEvent.cancel();
  }

  toggle = () => {
    const { collapsed, onCollapse } = this.props;
    onCollapse(!collapsed);
    this.triggerResizeEvent();
  };

  /* eslint-disable*/
  @Debounce(600)
  triggerResizeEvent() {
    const event = document.createEvent('HTMLEvents');
    event.initEvent('resize', true, false);
    window.dispatchEvent(event);
  }

  exitUserSession = () => {
    const { dispatch, store } = this.props;
    const sessionConfig = window.localStorage.getItem('persist:session');

    dispatch({
      type: 'global/exitUserSession',
    });
    dispatch({
      type: 'global/rehydrateSession',
      payload: JSON.parse(sessionConfig),
    });
    window.localStorage.removeItem('persist:session');
    dispatch(routerRedux.push('/'));
  };

  render() {
    const {
      collapsed,
      datastoreConfig,
      savingSession,
      sessionBannerVisible,
      sessionDescription,
      sessionId,
      isMobile,
      logo,
      dispatch,
    } = this.props;

    return (
      <div>
        {sessionBannerVisible && (
          <Alert
            message={sessionDescription}
            type="info"
            description={`Session ID: ${sessionId}`}
            closeText="Exit Session"
            icon={<Badge status="processing" />}
            onClose={this.exitUserSession}
            banner
          />
        )}
        <div className={styles.header}>
          <div style={{ display: 'flex', flexDirection: 'row' }}>
            {isMobile && [
              <Link to="/" className={styles.logo} key="logo">
                <img src={logo} alt="logo" width="32" />
              </Link>,
              <Divider type="vertical" key="line" />,
            ]}
            <Icon
              className={styles.trigger}
              type={collapsed ? 'menu-unfold' : 'menu-fold'}
              onClick={this.toggle}
            />
          </div>
          <div className={styles.right}>
            <SessionModal
              datastoreConfig={datastoreConfig}
              savingSession={savingSession}
              sessionConfig={this.props.store}
              dispatch={dispatch}
            />
            <Tooltip
              title="Search"
              onClick={() => {
                dispatch(
                  routerRedux.push({
                    pathname: '/search',
                  })
                );
              }}
            >
              <a className={styles.action}>
                <Icon type="search" />
              </a>
            </Tooltip>
            <Tooltip title="Help">
              <a
                target="_blank"
                href="https://docs.google.com/document/d/1W4-vUpMzClBxQmwODDG4WLENmHXrL-adf-5GOF-NYg8/edit"
                rel="noopener noreferrer"
                className={styles.action}
              >
                <Icon type="question-circle-o" />
              </a>
            </Tooltip>
          </div>
        </div>
      </div>
    );
  }
}

export default GlobalHeader;
