import React, { PropTypes } from 'react';
import {Table, Input, Button, LocaleProvider, enUS} from 'antd';
import history from '../../core/history';
import Layout from '../../components/Layout';
import CompareResults from '../../components/Comparison/CompareResults';
import constants from '../../core/constants';

class ComparisonPage extends React.Component {

  render() {
    let location = history.getCurrentLocation();

    return (
      <Layout>
        <LocaleProvider locale={enUS}>
          <CompareResults results={location.state.results}/>
        </LocaleProvider>
      </Layout>
    );
  }

}

export default ComparisonPage;
