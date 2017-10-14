import React, { PropTypes } from 'react';
import Layout from '../../components/Layout';
import WizardView from '../../components/Wizard/WizardView';
import c from '../common.css';

class EnvironmentsPage extends React.Component {

  state = { wizardView: false };

  componentDidMount() {
    document.title = 'Patternfly React Boiler | Environments';
  }

  handleClick = (event) => {
    this.setState({wizardView: true});
  };

  handleClose = (event) => {
    this.setState({wizardView: false});
  };

  render() {
    const { projects } = this.props;

    if(this.state.wizardView){
      return (
        <Layout className={c.add_layout}>
          <div className={c.add_container + ' container-pf-nav-pf-vertical'}>
            <div className={c.add_button} onClick={this.handleClick}>
              <i className="fa fa-4x fa-plus-circle" aria-hidden="true"></i>
              <h3>Add environments</h3>
            </div>
          </div>
          <WizardView handleClose={this.handleClose.bind(this)}/>
        </Layout>
      );
    } else {
      return (
        <Layout className={c.add_layout}>
          <div className={c.add_container + ' container-pf-nav-pf-vertical'}>
            <div className={c.add_button} onClick={this.handleClick}>
              <i className="fa fa-4x fa-plus-circle" aria-hidden="true"></i>
              <h3>Add environments</h3>
            </div>
          </div>
        </Layout>
      );
    }
  }

}

export default EnvironmentsPage;
