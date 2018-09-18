import numeral from 'numeral';
import 'components/Charts/g2';
import ChartCard from 'components/Charts/ChartCard';
import Bar from 'components/Charts/Bar';
import Pie from 'components/Charts/Pie';
import Radar from 'components/Charts/Radar';
import Gauge from 'components/Charts/Gauge';
import MiniArea from 'components/Charts/MiniArea';
import MiniBar from 'components/Charts/MiniBar';
import MiniProgress from 'components/Charts/MiniProgress';
import Field from 'components/Charts/Field';
import WaterWave from 'components/Charts/WaterWave';
import TagCloud from 'components/Charts/TagCloud';
import TimelineChart from 'components/Charts/TimelineChart';

const yuan = val => `¥ ${numeral(val).format('0,0')}`;

const Charts = {
  yuan,
  Bar,
  Pie,
  Gauge,
  Radar,
  MiniBar,
  MiniArea,
  MiniProgress,
  ChartCard,
  Field,
  WaterWave,
  TagCloud,
  TimelineChart,
};

export {
  Charts as default,
  yuan,
  Bar,
  Pie,
  Gauge,
  Radar,
  MiniBar,
  MiniArea,
  MiniProgress,
  ChartCard,
  Field,
  WaterWave,
  TagCloud,
  TimelineChart,
};
