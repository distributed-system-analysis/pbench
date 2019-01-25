import { PureComponent } from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Icon, Divider, Tooltip } from 'antd';
import Debounce from 'lodash-decorators/debounce';
import { Link } from 'dva/router';
import styles from './index.less';

@connect(({ routing }) => ({
  location: routing.location.pathname,
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

  render() {
    const { collapsed, isMobile, logo, location, dispatch } = this.props;
    console.log('header rendered');

    return (
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
    );
  }
}

export default connect(() => ({}))(GlobalHeader);
