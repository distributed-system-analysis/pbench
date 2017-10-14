import React from 'react';


class EmptyState extends React.Component {

  render() {

    return (
        <div className="row">
          <div className="col-md-12">

            <div className="page-header">
              <h1>{ this.props.title }</h1>
            </div>

            <div className="blank-slate-pf">
              <div className="blank-slate-pf-icon">
                <i className="fa fa-rocket"></i>
              </div>
              <h1>Empty State Title</h1>
              <p>Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.</p>
              <p>Learn more about this <a href="#">on the documentation</a>.</p>
              <div className="blank-slate-pf-main-action">
                <button className="btn btn-primary btn-lg">
                  Main Action
                </button>
              </div>
              <div className="blank-slate-pf-secondary-action">
                <button className="btn btn-default">
                  Secondary Action
                </button>
                <button className="btn btn-default">
                  Secondary Action
                </button>
                <button className="btn btn-default">
                  Secondary Action
                </button>
              </div>
            </div>

          </div>
        </div>
    );
  }

}

export default EmptyState;
