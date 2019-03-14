import React from 'react';
import { connect } from 'dva';
import { routerRedux } from 'dva/router';
import { Spin } from 'antd';

@connect(store => ({
  datastoreConfig: store.datastore.datastoreConfig,
  store,
}))
class SessionPlaceholder extends React.Component {
  componentDidMount = () => {
    this.queryDatastoreConfig();
  };

  queryDatastoreConfig = async () => {
    const { dispatch } = this.props;

    dispatch({
      type: 'datastore/fetchDatastoreConfig',
    }).then(() => {
      this.persistCurrentSession();
    });
  };

  persistCurrentSession = () => {
    const { store } = this.props;

    const parsedSessionConfig = JSON.stringify(store);
    Promise.resolve(window.localStorage.setItem('persist:session', parsedSessionConfig)).then(
      () => {
        this.queryUserSession();
      }
    );
  };

  queryUserSession = async () => {
    const { dispatch, datastoreConfig } = this.props;
    const path = window.location.href;
    const id = path.substring(path.lastIndexOf('/') + 1);

    dispatch({
      type: 'global/fetchUserSession',
      payload: {
        id,
        datastoreConfig,
      },
    }).then(response => {
      this.rehydrateNamespaces(response.sessionConfig, response.sessionMetadata);
    });
  };

  rehydrateNamespaces = async (sessionConfig, sessionMetadata) => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/rehydrateSession',
      payload: sessionConfig,
    }).then(() => {
      this.startUserSession(sessionConfig, sessionMetadata);
    });
  };

  startUserSession = async (sessionConfig, sessionMetadata) => {
    const { dispatch } = this.props;

    dispatch({
      type: 'global/startUserSession',
      payload: {
        render: true,
        sessionDescription: sessionMetadata.description,
        sessionId: sessionMetadata.id,
      },
    });
    dispatch(routerRedux.push(sessionConfig.routing.location.pathname));
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
