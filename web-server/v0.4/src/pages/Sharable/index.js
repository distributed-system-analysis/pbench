import React from 'react';
import { connect } from 'dva';
import { Spin } from 'antd';

@connect(store => ({
  store,
}))
class Sharable extends React.Component {
  static propTypes = {};

  constructor(props) {
    super(props);

    this.state = {
      spinnerLoading: true,
    };
  }

  componentDidMount = () => {
    const { dispatch } = this.props;
    const path = window.location.href;
    const id = path.substring(path.lastIndexOf('/') + 1);

    dispatch({
      type: 'dashboard/fetchSharedConfig',
      payload: {
        id,
      },
    }).then(() => {
      // dispatch(routerRedux.push('/comparison'));
    });
    this.setState({
      spinnerLoading: false,
    });
  };

  render() {
    const { spinnerLoading } = this.state;
    return (
      <div style={{ textAlign: 'center', marginTop: '20%' }}>
        <h1>Hi there...</h1>
        <Spin spinning={spinnerLoading} size="large" />
      </div>
    );
  }
}

export default connect(() => ({}))(Sharable);
