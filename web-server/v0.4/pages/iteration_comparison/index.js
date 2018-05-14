import React, { PropTypes } from 'react';
import {Table, Input, Button, LocaleProvider} from 'antd';
import history from '../../core/history';
import enUS from 'antd/lib/locale-provider/en_US';
import Layout from '../../components/Layout';
import CompareIterations from '../../components/Comparison/CompareIterations';
import constants from '../../core/constants';

class IterationComparisonPage extends React.Component {

  render() {
    let location = history.getCurrentLocation();
    
    var primaryMetricPos = location.state.configCategories.indexOf('primary_metric');
    location.state.configCategories.splice(primaryMetricPos, 1);

    return (
      <Layout>
        <LocaleProvider locale={enUS}>
          <CompareIterations iterations={location.state.iterations} configCategories={location.state.configCategories} configData={location.state.configData} results={location.state.results} controller={location.state.controller}/>
        </LocaleProvider>
      </Layout>
    );
  }
}

export default IterationComparisonPage;
