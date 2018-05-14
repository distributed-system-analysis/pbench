import React from 'react';
import { LocaleProvider } from 'antd';
import enUS from 'antd/lib/locale-provider/en_US';
import NetworkException from '../../components/Util/Exception';
import Layout from '../../components/Layout';

class Exception extends React.Component {

  render() {
    return (
      <Layout>
        <LocaleProvider locale={enUS}>
          <NetworkException/>
        </LocaleProvider>
      </Layout>
    );
  }

}

export default Exception;
