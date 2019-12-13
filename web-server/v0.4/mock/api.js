import config from './datastoreConfig';
import constants from '../config/constants';

// Generate controllers as per max page size options
const maxTableSize = parseInt(constants.tableSizeOptions.pop(), 10);
let generatedBuckets = new Array(maxTableSize).fill({});
generatedBuckets = generatedBuckets.map((val, index) => {
  const key = index + 1;
  return {
    key: `controller_${key}`,
    doc_count: key,
    runs_prev1: { value: null },
    runs: { value: key, value_as_string: key.toString() },
  };
});
export const generateMockControllerAggregation = {
  aggregations: {
    controllers: {
      buckets: generatedBuckets,
    },
  },
};

const datastoreConfig = config['/dev/datastoreConfig'];
const prefix = datastoreConfig.prefix + datastoreConfig.run_index.slice(0, -1);
export const mockIndices = [
  {
    index: `${prefix}.0000-00-00`,
  },
  {
    index: `${prefix}.0000-00-01`,
  },
];

export const mockResults = {
  hits: {
    hits: [
      {
        fields: {
          'run.name': ['a_test_run'],
          '@metadata.controller_dir': ['test_run.test_domain.com'],
          'run.start': ['1111-11-11T11:11:11+00:00'],
          'run.id': ['1111'],
          'run.end': ['1111-11-11T11:11:12+00:00'],
          'run.controller': ['test_run.test_domain.com'],
          'run.config': ['test_size_1'],
        },
      },
      {
        fields: {
          'run.name': ['b_test_run'],
          '@metadata.controller_dir': ['b_test_run.test_domain.com'],
          'run.start': ['1111-11-11T11:11:13+00:00'],
          'run.id': ['2222'],
          'run.end': ['1111-11-11T11:11:14+00:00'],
          'run.controller': ['b_test_run.test_domain.com'],
          'run.config': ['test_size_2'],
        },
      },
    ],
  },
};

export const mockMappings = {
  [`${prefix}.0000-00-00`]: {
    mappings: {
      'pbench-run': {
        properties: {
          run: {
            properties: {
              config: { type: 'string', index: 'not_analyzed' },
              name: { type: 'string', index: 'not_analyzed' },
              script: { type: 'string', index: 'not_analyzed' },
              user: { type: 'string', index: 'not_analyzed' },
            },
          },
          '@metadata': {
            properties: {
              controller_dir: { type: 'string', index: 'not_analyzed' },
            },
          },
        },
      },
    },
  },
};

export const mockSearch = {
  hits: {
    total: 1,
    hits: [
      {
        _id: '1111',
        fields: {
          'run.config': ['test-size-1'],
          'run.name': ['test_run'],
          'run.script': ['test_controller'],
          'run.user': ['test_user'],
          '@metadata.controller_dir': ['test_controller'],
        },
      },
    ],
  },
};

export const mockStore = {
  router: {},
  dashboard: {},
  search: {},
  store: {},
};
