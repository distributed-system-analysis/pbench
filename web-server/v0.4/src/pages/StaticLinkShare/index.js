import React from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Spin } from 'antd';

@connect(({ routing }) => ({
  pathname: routing.location.pathname,
}))
class Sharable extends React.Component {
  componentDidMount = () => {
    const { dispatch, pathname } = this.props;
    const path = window.location.href;
    const id = path.substring(path.lastIndexOf('/') + 1);
    dispatch({
      type: 'dashboard/fetchSharedConfig',
      payload: {
        id,
      },
    }).then(dispatch(routerRedux.push(pathname)));
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

export default connect(() => ({}))(Sharable);
