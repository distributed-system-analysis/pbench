import React from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Spin } from 'antd';

<<<<<<< HEAD
@connect(({ global }) => ({
  datastoreConfig: global.datastoreConfig,
}))
class SessionPlaceholder extends React.Component {
  componentDidMount = () => {
    const { dispatch, datastoreConfig } = this.props;
=======
@connect(() => ({}))
class SessionPlaceholder extends React.Component {
  componentDidMount = () => {
    const { dispatch } = this.props;
>>>>>>> Resolve location change on config load callback
    const path = window.location.href;
    const id = path.substring(path.lastIndexOf('/') + 1);
    dispatch({
      type: 'dashboard/fetchSharedConfig',
      payload: {
        id,
<<<<<<< HEAD
        datastoreConfig,
=======
>>>>>>> Resolve location change on config load callback
      },
    }).then(config => {
      dispatch(routerRedux.push(config.routing.location.pathname));
    });
  };

  render() {
    return (
      <div
        style={{
          display: 'flex',
        }}
      >
        <Spin
          style={{
            flex: 1,
            justifyContent: 'center',
            alignItems: 'center',
          }}
          spinning
          tip="Retrieving dashboard session..."
          size="large"
        />
      </div>
    );
  }
}

export default connect(() => ({}))(SessionPlaceholder);
