import React, { PropTypes } from 'react';
import Layout from '../../components/Layout';
import AppListView from '../../components/ListView/AppListView';
import constants from '../../core/constants';

class AppsPage extends React.Component {

  state = { apps: [] };

  componentDidMount() {
    document.title = 'Patternfly React Boiler | Apps';
  }

  componentWillMount() {
    this.getApps();
  }

  getApps() {
    let that = this;
    fetch(constants.get_apps_url).then(r => r.json())
      .then(data => {
        that.setState({apps : data})
      })
      .catch(e => console.log("Booo"));
  }

  render() {
    return (
      <Layout className="container-fluid container-pf-nav-pf-vertical">
        <AppListView apps={ this.state.apps }/>
      </Layout>
    );
  }

}

export default AppsPage;
