import React, { PureComponent } from 'react';
import PropTypes from 'prop-types';
import jschart from 'jschart';

export default class TimeseriesGraph extends PureComponent {
  static propTypes = {
    dataSeriesNames: PropTypes.array.isRequired,
    data: PropTypes.array.isRequired,
    graphId: PropTypes.string.isRequired,
    graphName: PropTypes.string,
    graphOptions: PropTypes.object,
    xAxisSeries: PropTypes.string.isRequired,
    xAxisTitle: PropTypes.string,
    yAxisTitle: PropTypes.string,
  };

  static defaultProps = {
    graphName: null,
    graphOptions: {},
    xAxisTitle: null,
    yAxisTitle: null,
  };

  componentDidMount = () => {
    const {
      xAxisSeries,
      dataSeriesNames,
      data,
      graphId,
      graphName,
      xAxisTitle,
      yAxisTitle,
      graphOptions,
    } = this.props;

    jschart.create_jschart(0, 'timeseries', graphId, graphName, xAxisTitle, yAxisTitle, {
      dynamic_chart: true,
      json_object: {
        x_axis_series: xAxisSeries,
        data_series_names: dataSeriesNames,
        data,
      },
      ...graphOptions,
    });
  };

  componentDidUpdate = prevProps => {
    const { data, dataSeriesNames, xAxisSeries, graphId } = this.props;
    if (
      JSON.stringify(prevProps.data) !== JSON.stringify(data) ||
      JSON.stringify(prevProps.dataSeriesNames) !== JSON.stringify(dataSeriesNames) ||
      prevProps.xAxisSeries !== xAxisSeries
    ) {
      jschart.chart_reload(graphId, {
        json_object: {
          x_axis_series: xAxisSeries,
          data_series_names: dataSeriesNames,
          data,
        },
      });
    }
  };

  render() {
    const { graphId } = this.props;

    return <div id={graphId} />;
  }
}
