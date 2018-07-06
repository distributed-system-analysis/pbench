import React, { PropTypes } from 'react';
import {Table, Input, Button, LocaleProvider} from 'antd';
import history from '../../core/history';
import enUS from 'antd/lib/locale-provider/en_US';
import Layout from '../../components/Layout';
import Summary from '../../components/Layout/Summary';
import constants from '../../core/constants';

class UsersPage extends React.Component {

  render() {
    let location = history.getCurrentLocation();

    return (
      <Layout>
        <LocaleProvider locale={enUS}>
          <Summary result={location.state.result} controller={location.state.controller}/>
        </LocaleProvider>
      </Layout>
    );
  }

}

export default UsersPage;
