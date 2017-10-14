import React, { PropTypes } from 'react';
import Layout from '../../components/Layout';
import EmptyState from '../../components/EmptyState/EmptyState';

class StagesPage extends React.Component {

  componentDidMount() {
    document.title = 'Patternfly React Boiler | Stages';
  }

  render() {
    return (
      <Layout className="container-fluid container-pf-nav-pf-vertical">
        <EmptyState title="Stages"/>
      </Layout>
    );
  }

}

export default StagesPage;
