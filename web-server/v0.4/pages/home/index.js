import React, { PropTypes } from 'react';
import Layout from '../../components/Layout';
import ControllerListView from '../../components/ListView/ControllerListView';
import constants from '../../core/constants';

class HomePage extends React.Component {

  render() {
    return (
      <Layout>
        <ControllerListView/>
      </Layout>
    );
  }

}

export default HomePage;
