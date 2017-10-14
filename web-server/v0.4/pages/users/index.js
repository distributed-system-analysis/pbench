import React, { PropTypes } from 'react';
import Layout from '../../components/Layout';
import CardView from '../../components/CardView/CardView';
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
    if(this.state.users.length){
      return (
        <Layout>
          <div className="container-fluid container-pf-nav-pf-vertical container-cards-pf">
            <CardView users={ this.state.users } />
          </div>
        </Layout>
      );
    }
    return (
      <Layout>
        <div className="container-fluid container-pf-nav-pf-vertical container-cards-pf">
        </div>
      </Layout>
    );
  }

}

export default UsersPage;
