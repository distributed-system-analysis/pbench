import React, { PropTypes } from 'react';
import {Table, Input, Button, LocaleProvider} from 'antd';
import history from '../../core/history';
import enUS from 'antd/lib/locale-provider/en_US';
import Layout from '../../components/Layout';
import ResultListView from '../../components/ListView/ResultListView';
import constants from '../../core/constants';

class UsersPage extends React.Component {

  render() {
    let location = history.getCurrentLocation();

    return (
      <Layout>
        <ResultListView controller={location.state.controller}/>
      </Layout>
    );
  }

}

export default UsersPage;
