import React, { PropTypes } from 'react';

class AppListView extends React.Component {

  componentDidMount() {
    this.bindExpand();
  }

  componentDidUpdate() {
    this.unbind();
    this.bindExpand();
  }

  componentWillUnmount(){
    this.unbind();
  }

  bindExpand() {
    // click the list-view heading then expand a row
    $(".list-group-item-header").click(function(event){
      if(!$(event.target).is("button, a, input, .fa-ellipsis-v")){
        $(this).find(".fa-angle-right").toggleClass("fa-angle-down")
          .end().parent().toggleClass("list-view-pf-expand-active")
          .find(".list-group-item-container").toggleClass("hidden");
      }
    });

    // click the close button, hide the expand row and remove the active status
    $(".list-group-item-container .close").on("click", function (){
      $(this).parent().addClass("hidden")
        .parent().removeClass("list-view-pf-expand-active")
        .find(".fa-angle-right").removeClass("fa-angle-down");
    });
  }
  
  unbind() {
    $(".list-group-item-header").off('click');
    $(".list-group-item-container .close").off('click');
  }

  render() {
    const { apps } = this.props; // eslint-disable-line no-use-before-define

    return (
      <div className="list-group list-view-pf list-view-pf-view">

        {apps.map((app,i) =>
        <div className="list-group-item" key={i}>
          
          <div className="list-group-item-header">
            <div className="list-view-pf-expand">
              <span className="fa fa-angle-right"></span>
          </div>
          <div className="list-view-pf-actions">
            <button className="btn btn-default">Action</button>
          </div>
          <div className="list-view-pf-main-info">
            <div className="list-view-pf-left">
              <span className="fa fa-plane list-view-pf-icon-sm"></span>
            </div>
            <div className="list-view-pf-body">
              <div className="list-view-pf-description">
                <div className="list-group-item-heading">
                  { app.name }
                </div>
              </div>
              <div className="list-view-pf-additional-info">
                <div className="list-view-pf-additional-info-item">
                  <span className="pficon pficon-screen"></span>
                  <strong>8</strong> Hosts
                </div>
                <div className="list-view-pf-additional-info-item">
                  <span className="pficon pficon-cluster"></span>
                  <strong>6</strong> Clusters
                </div>
                <div className="list-view-pf-additional-info-item">
                  <span className="pficon pficon-container-node"></span>
                  <strong>10</strong> Nodes
                </div>
                <div className="list-view-pf-additional-info-item">
                  <span className="pficon pficon-image"></span>
                  <strong>8</strong> Images
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="list-group-item-container container-fluid hidden">
          <div className="close">
            <span className="pficon pficon-close"></span>
          </div>
          <div className="row">
            <div className="col-md-3">
            </div>
            <div className="col-md-9">
              <dl className="dl-horizontal">
                <dt>Host Name</dt>
                <dd>Hostceph1</dd>
                <dt>Device Path</dt>
                <dd>/dev/disk/pci-0000.05:00-sas-0.2-part1</dd>
                <dt>Time</dt>
                <dd>January 15, 2016 10:45:11 AM</dd>
                <dt>Severity</dt>
                <dd>Warning</dd>
                <dt>Cluster</dt>
                <dd>Cluster 1</dd>
              </dl>
              <p>
                { app.description }
              </p>
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
    )
  }

}

export default AppListView;
