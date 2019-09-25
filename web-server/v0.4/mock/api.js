import config from './datastoreConfig';

export const mockControllerAggregation = {
  aggregations: {
    controllers: {
      buckets: [
        {
          key: 'a_test_controller',
          doc_count: 1,
          runs_preV1: { value: null },
          runs: { value: 1, value_as_string: '1111-11-11' },
        },
        {
          key: 'b_test_controller',
          doc_count: 2,
          runs_preV1: { value: null },
          runs: { value: 2, value_as_string: '2222-22-22' },
        },
      ],
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
        _source: {
          run: {
            config: 'test-size-1',
            name: 'test_run',
            script: 'test',
            user: 'test_user',
          },
          '@metadata': {
            controller_dir: 'test_controller',
          },
        },
      },
    ],
  },
};
