import React from 'react';
import Link from '../Link';
import datastore from '../../utils/datastore';

function Header() {
  return (
    <nav className="navbar navbar-pf-vertical">
      <div className="navbar-header">
        <Link to="/dashboard" className="navbar-brand">
          <h4 style={{marginTop: 8, color: 'white'}}>PBench Dashboard</h4>
        </Link>
      </div>
      <nav className="collapse navbar-collapse">
        <ul className="nav navbar-nav navbar-right navbar-iconic">
          <li className="dropdown">
            <a className="dropdown-toggle nav-item-iconic" id="dropdownMenu1" data-toggle="dropdown" aria-haspopup="true" aria-expanded="true">
              <span title="Help" className="fa pficon-help"></span>
              <span className="caret"></span>
            </a>
            <ul className="dropdown-menu" aria-labelledby="dropdownMenu1">
              <li><a href="https://github.com/distributed-system-analysis/pbench/issues/new?labels=Pbench+Dashboard&assignee=gurbirkalsi" target="_blank">Report Issue</a></li>
              <li><a href={datastore.pbench_server} target="_blank">About</a></li>
            </ul>
          </li>
        </ul>
      </nav>
    </nav>
  );
}

export default Header;
