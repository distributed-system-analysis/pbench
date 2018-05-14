import React from "react";
import Exception from 'ant-design-pro/lib/Exception';
import { Button } from 'antd';
import history from '../../core/history';

export default class NetworkException extends React.Component {

    goBack = () => {
        history.go(-2)
    }

    render() {

        const actions = (
            <div>
              <Button type="primary" onClick={this.goBack}>{'Back'}</Button>
            </div>
        );

        return (
            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 64}} className="container-fluid container-pf-nav-pf-vertical">
                <Exception type="404" title="Could not find resources." desc="The following tool data collections are supported: uperf" actions={actions}/>
            </div>
        )
    }
}