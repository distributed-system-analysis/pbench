import React, { PropTypes } from 'react';
import {Table, Input, Button, LocaleProvider} from 'antd';
import history from '../../core/history';
import enUS from 'antd/lib/locale-provider/en_US';
import Layout from '../../components/Layout';
import IterationSummary from '../../components/Layout/IterationSummary';
import constants from '../../core/constants';

class IterationSummaryPage extends React.Component {

  render() {
    let location = history.getCurrentLocation();

    return (
      <Layout>
        <LocaleProvider locale={enUS}>
          <IterationSummary/>
        </LocaleProvider>
      </Layout>
    );
  }
}

export default IterationSummaryPage;
