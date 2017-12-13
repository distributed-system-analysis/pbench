import React, {PropTypes} from 'react';
import history from '../../core/history';
import { Spin, Tag, Table, Input, Button, LocaleProvider} from 'antd';
import enUS from 'antd/lib/locale-provider/en_US';
import axios from 'axios';
import DOMParser from 'react-native-html-parser';

class IterationSummary extends React.Component {
  static propTypes = {
    result: React.PropTypes.string,
    controller: React.PropTypes.string,
    iteration_name: React.PropTypes.string,
    sample: React.PropTypes.string
  };

  constructor(props) {
    super(props);

    this.state = {
    }
  }

  componentWillMount() {
    const script1 = document.createElement("script");
    script1.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/d3.min.js";
    script1.async = true;

    const script2 = document.createElement("script");
    script2.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/d3-queue.min.js";
    script2.async = true;

    const script3 = document.createElement("script");
    script3.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/saveSvgAsPng.js";
    script3.async = true;

    const script4 = document.createElement("script");
    script4.src = "http://pbench.perf.lab.eng.bos.redhat.com/static/js/v0.3/jschart.js";
    script4.async = true;

    document.body.appendChild(script1);
    document.body.appendChild(script2);
    document.body.appendChild(script3);
    document.body.appendChild(script4);
  }

  iframe() {
    return {
      __html: '<iframe src="http://pbench.perf.lab.eng.bos.redhat.com/results/' + window.location.href.split('results/').pop() + '/uperf.html" width="100%" height="2000"></iframe>'
    }
  }

  render() {
      return (
        <div style={{ marginLeft: 70 }}>
          <div dangerouslySetInnerHTML={this.iframe()}/>
        </div>
      );
  }
}

export default IterationSummary;
