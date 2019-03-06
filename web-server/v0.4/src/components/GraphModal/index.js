import React, { PureComponent } from 'react';
import { Modal } from 'antd';
import TimeseriesGraph from '../TimeseriesGraph';

export default class GraphModal extends PureComponent {
  constructor(props) {
    super(props);
    this.timeseriesGraph = React.createRef();

    this.state = {
      visible: false,
    };
  }

  handleShow = () => {
    this.setState({
      visible: true,
    });
  };

  handleHide = () => {
    this.setState({
      visible: false,
    });
  };

  render() {
    const { sampleNumber, graphId, timeseriesData, dataSeries, modalTitle } = this.props;
    const { visible } = this.state;
    return (
      <div>
        <a onClick={this.handleShow}>{sampleNumber}</a>
        <Modal
          centered
          visible={visible}
          onOk={this.handleHide}
          onCancel={this.handleHide}
          width={this.timeseriesGraph}
        >
          <TimeseriesGraph
            ref={this.timeseriesGraph}
            graphId={graphId}
            graphName={modalTitle}
            data={timeseriesData}
            dataSeriesNames={dataSeries}
            xAxisSeries="time"
          />
        </Modal>
      </div>
    );
  }
}
