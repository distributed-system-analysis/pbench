import ReactJS, { Component } from 'react';
import { connect } from 'dva';
import PageHeaderLayout from '../../layouts/PageHeaderLayout';

@connect()
export default class SearchList extends Component {
  constructor(props) {
    super(props);
  }

  render() {

    return (
      <PageHeaderLayout>
      </PageHeaderLayout>
    );
  }
}
