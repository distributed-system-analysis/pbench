import React, { PropTypes } from 'react';
import Layout from '../../components/Layout';
import ControllerListView from '../../components/ListView/ControllerListView';
import constants from '../../core/constants';

class HomePage extends React.Component {

  state = { projects: [] };

  componentDidMount() {
    document.title = 'Patternfly React Boiler | Home';
  }

  componentWillMount() {
    this.getProjects();
  }

  getProjects() {
    let that = this;
    fetch(constants.get_projects_url).then(r => r.json())
      .then(data => {
        that.setState({projects : data})
      })
      .catch(e => console.log("Booo"));
  }

  render() {
    return (
      <Layout>
        <ControllerListView/>
      </Layout>
    );
  }

}

export default HomePage;
