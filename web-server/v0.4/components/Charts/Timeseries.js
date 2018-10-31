import React from 'react';
import { Chart, Tooltip, Geom, Legend, Axis } from 'bizcharts';
import DataSet from '@antv/data-set';
import Slider from 'bizcharts-plugin-slider';

class Timeseries extends React.Component {
  render() {
    const {
      title,
      height = 400,
      padding = [100, 100, 40, 100],
      titleMap = {},
      borderWidth = 2,
      data = [],
    } = this.props;

    data.sort((a, b) => a.x - b.x);

    var sortingQueue = [];
    var fields = [];
    Object.keys(titleMap).map(iteration => {
        fields.push(titleMap[iteration]);
        sortingQueue.push([...data].sort((a, b) => b[iteration] - a[iteration])[0][iteration]);
    })

    let max;
    if (data[0]) {
      max = Math.max(...sortingQueue);
    }

    const ds = new DataSet({
        state: {
            start: data[0].x,
            end: data[data.length - 1].x,
        },
    });

    //dv transforms the passed in timeseries data properties to the appropriate schema needed for visualization.
    const dv = ds.createView();
    dv
      .source(data)
      .transform({
        type: 'filter',
        callback: obj => {
          const date = obj.x;
          return date <= ds.state.end && date >= ds.state.start;
        },
      })
      .transform({
        type: 'map',
        callback(row) {
          const newRow = { ...row };
          for (var key in Object.keys(titleMap)) {
            newRow[titleMap[Object.keys(titleMap)[key]]] = row[Object.keys(titleMap)[key]];
          }
          return newRow;
        },
      })
      .transform({
        type: 'fold',
        fields: fields,
        key: 'key',
        value: 'value',
      });

    const timeScale = {
      type: 'time',
      tickInterval: 60 * 60 * 1000,
      mask: 'HH:mm:ss',
      range: [0, 1],
    };

    const cols = {
      x: timeScale,
      value: {
        max,
        min: 0,
      },
    };

    const SliderGen = () => (
      <Slider
        padding={[0, padding[1] + 20, 0, padding[3]]}
        width="auto"
        height={26}
        xAxis="x"
        yAxis="y1"
        scales={{ x: timeScale }}
        data={data}
        start={ds.state.start}
        end={ds.state.end}
        backgroundChart={{ type: 'line' }}
        onChange={({ startValue, endValue }) => {
          ds.setState('start', startValue);
          ds.setState('end', endValue);
        }}
      />
    );

    return (
      <div style={{ background: 'white', height: height + 30 }}>
        <div>
          {title && <h4>{title}</h4>}
          <Chart height={height} padding={padding} data={dv} scale={cols} forceFit>
            <Axis name="x" />
            <Tooltip />
            <Legend name="key" position="top" />
            <Geom type="line" position="x*value" size={borderWidth} color="key" />
          </Chart>
          <div style={{ marginRight: -20 }}>
            <SliderGen />
          </div>
        </div>
      </div>
    );
  }
}

export default Timeseries;