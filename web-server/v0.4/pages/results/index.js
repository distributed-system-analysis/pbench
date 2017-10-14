import React, { PropTypes } from 'react';
import {Table, Input, Button, LocaleProvider} from 'antd';
import history from '../../core/history';
import enUS from 'antd/lib/locale-provider/en_US';
import Layout from '../../components/Layout';
import ResultListView from '../../components/ListView/ResultListView';
import constants from '../../core/constants';

class UsersPage extends React.Component {

  state = { users: [] };

  componentDidMount() {
    document.title = 'Patternfly React Boiler | Users';
  }

  componentWillMount() {
    this.getUsers();
  }

  getUsers() {
    let that = this;
    fetch(constants.get_users_url).then(r => r.json())
      .then(data => {
        that.setState({users : data})
      })
      .catch(e => console.log(e));
  }

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
