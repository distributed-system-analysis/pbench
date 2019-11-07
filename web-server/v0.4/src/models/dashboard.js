import _ from 'lodash';
import {
  queryControllers,
  queryResults,
  queryResult,
  queryTocResult,
  queryIterationSamples,
  queryTimeseriesData,
} from '../services/dashboard';

import { insertTocTreeData } from '../utils/utils';

export default {
  namespace: 'dashboard',

  state: {
    result: [],
    results: {},
    iterationParams: {},
    iterations: [],
    controllers: [],
    tocResult: [],
    loading: false,
  },

  effects: {
    *fetchControllers({ payload }, { call, put }) {
      const response = yield call(queryControllers, payload);
      const controllers = [];

      response.aggregations.controllers.buckets.forEach(controller => {
        let lastModVal;
        let lastModStr;
        if (controller.runs.value) {
          // Look for v1 data
          lastModVal = controller.runs.value;
          lastModStr = controller.runs.value_as_string;
        } else {
          // Fall back to pre-v1 data
          lastModVal = controller.runs_preV1.value;
          lastModStr = controller.runs_preV1.value_as_string;
        }
        controllers.push({
          key: controller.key,
          controller: controller.key,
          results: controller.doc_count,
          last_modified_value: lastModVal,
          last_modified_string: lastModStr,
        });
      });

      yield put({
        type: 'getControllers',
        payload: controllers,
      });
    },
    *fetchResults({ payload }, { call, put }) {
      const response = yield call(queryResults, payload);
      const runs = [];

      response.hits.hits.forEach(result => {
        const { fields } = result;
        const name = fields['run.name'].shift();
        const controller = fields['run.controller'].shift();
        const id = fields['run.id'].shift();
        const start =
          typeof fields['run.start'] !== 'undefined'
            ? fields['run.start'][0]
            : fields['run.start_run'][0];
        const end =
          typeof fields['run.end'] !== 'undefined'
            ? fields['run.end'][0]
            : fields['run.end_run'][0];

        const record = {
          key: name,
          startUnixTimestamp: Date.parse(start),
          'run.name': name,
          'run.controller': controller,
          'run.start': start,
          'run.end': end,
          id,
        };

        if (typeof fields['run.config'] !== 'undefined') {
          record['run.config'] = fields['run.config'].shift();
        }
        if (typeof fields['run.prefix'] !== 'undefined') {
          record['run.prefix'] = fields['run.prefix'].shift();
        }
        if (typeof fields['@metadata.controller_dir'] !== 'undefined') {
          record['@metadata.controller_dir'] = fields['@metadata.controller_dir'].shift();
        }
        if (typeof fields['@metadata.satellite'] !== 'undefined') {
          record['@metadata.satellite'] = fields['@metadata.satellite'].shift();
        }
        runs.push(record);
      });

      const results = {};
      results[payload.controller[0]] = runs;

      yield put({
        type: 'getResults',
        payload: results,
      });
    },
    *fetchResult({ payload }, { call, put }) {
      const response = yield call(queryResult, payload);
      const result =
        // eslint-disable-next-line no-underscore-dangle
        typeof response.hits.hits[0] !== 'undefined' ? response.hits.hits[0]._source : [];
      let metadataTag = '';
      const parsedResult = {};

      if (typeof result['@metadata'] !== 'undefined') {
        metadataTag = '@metadata';
      } else {
        metadataTag = '_metadata';
      }

      parsedResult.runMetadata = {
        ...result.run,
        ...result[metadataTag],
      };

      parsedResult.hostTools = [];
      result.host_tools_info.forEach(toolData => {
        parsedResult.hostTools.push(toolData);
      });

      yield put({
        type: 'getResult',
        payload: parsedResult,
      });
    },
    *fetchTocResult({ payload }, { call, put }) {
      const response = yield call(queryTocResult, payload);
      const tocResult = {};

      response.hits.hits.forEach(result => {
        // eslint-disable-next-line no-underscore-dangle
        const source = result._source;

        if (source.files !== undefined) {
          source.files.forEach(path => {
            const url = source.directory + path.name;
            tocResult[url] = [path.size, path.mode];
          });
        }
      });

      const tocTree = Object.keys(tocResult)
        .map(path => path.split('/').slice(1))
        .reduce((items, path) => insertTocTreeData(tocResult, items, path), []);

      yield put({
        type: 'getTocResult',
        payload: tocTree,
      });
    },
    *fetchIterationSamples({ payload }, { call, put }) {
      const response = yield call(queryIterationSamples, payload);
      const runs = {};
      const iterations = {};
      let iterationParams = {};
      const paramBlacklist = [
        '@idx',
        'description',
        'end',
        'max_stddevpct',
        'mean',
        'measurement_idx',
        'name',
        'start',
        'stddev',
        'stddevpct',
        'uid_tmpl',
      ];

      response.forEach(run => {
        const id = run.aggregations.id.buckets[0].key;
        run.hits.hits.forEach(sample => {
          // eslint-disable-next-line no-underscore-dangle
          const source = sample._source;
          if (source.iteration.name.includes('fail')) {
            return;
          }
          const sampleSource = _.omit({ ...source.benchmark, ...source.sample }, paramBlacklist);

          // Aggregate iteration params
          iterationParams = _.mergeWith(iterationParams, sampleSource, (objVal, srcVal) => {
            if (objVal !== undefined) {
              const uniqParams = _.uniq([...objVal, ...[srcVal]]);
              return uniqParams;
            }
            return [srcVal];
          });

          // Aggregate iteration samples
          const sampleData = {};
          const sampleFields = source.sample;
          const benchmarkFields = source.benchmark;
          const runFields = source.run;
          const iterationFields = source.iteration;

          const samplePrefix = [
            sampleFields.measurement_type,
            sampleFields.measurement_title,
            sampleFields.uid,
          ]
            .join('-')
            .toLowerCase();
          sampleData[`${samplePrefix}-closest_sample`] = sampleFields.closest_sample;
          sampleData[`${samplePrefix}-mean`] = sampleFields.mean;
          sampleData[`${samplePrefix}-stddevpct`] = sampleFields.stddevpct;
          iterationFields.closest_sample = sampleFields.closest_sample;

          iterations[source.iteration.name] = {
            ...iterations[source.iteration.name],
            ...iterationFields,
            ...sampleData,
            [sampleFields.name]: {
              ...((iterations[source.iteration.name] || {})[sampleFields.name] || {}),
              [sampleFields.uid]: {
                ...sampleFields,
                ...benchmarkFields,
                ...runFields,
              },
            },
          };
        });

        run.aggregations.id.buckets.forEach(runId => {
          const iterationColumnsData = [
            {
              title: 'Iteration Name',
              dataIndex: 'name',
              key: 'name',
            },
          ];
          runId.type.buckets.forEach(type => {
            iterationColumnsData.push({
              title: type.key,
              children: type.title.buckets.map(title => {
                return {
                  title: title.key,
                  children: title.uid.buckets.map(uid => {
                    return {
                      title: `${type.key}-${title.key}-${uid.key}`,
                      children: [
                        {
                          title: 'mean',
                          dataIndex: `${type.key}-${title.key}-${uid.key}-mean`,
                          key: `${type.key}-${title.key}-${uid.key}-mean`,
                        },
                        {
                          title: 'stddevpct',
                          dataIndex: `${type.key}-${title.key}-${uid.key}-stddevpct`,
                          key: `${type.key}-${title.key}-${uid.key}-stddevpct`,
                        },
                        {
                          title: 'closest_sample',
                          dataIndex: `${type.key}-${title.key}-${uid.key}-closest_sample`,
                          key: `${type.key}-${title.key}-${uid.key}-closest_sample`,
                        },
                      ],
                    };
                  }),
                };
              }),
            });
          });
          runs[runId.key] = { columns: iterationColumnsData };
        });
        runs[id] = {
          ...runs[id],
          run_name: run.aggregations.name.buckets[0].key,
          run_controller: run.aggregations.controller.buckets[0].key,
          iterations,
          id,
        };
      });

      yield put({
        type: 'modifyConfigCategories',
        payload: iterationParams,
      });
      yield put({
        type: 'getIterations',
        payload: runs,
      });
    },
    *fetchTimeseriesData({ payload }, { call }) {
      const response = yield call(queryTimeseriesData, payload);

      return response;
    },
    *updateConfigCategories({ payload }, { put }) {
      yield put({
        type: 'modifyConfigCategories',
        payload,
      });
    },
    *updateConfigData({ payload }, { put }) {
      yield put({
        type: 'modifyConfigData',
        payload,
      });
    },
  },

  reducers: {
    getControllers(state, { payload }) {
      return {
        ...state,
        controllers: payload,
      };
    },
    getResults(state, { payload }) {
      return {
        ...state,
        results: { ...state.results, ...payload },
      };
    },
    getResult(state, { payload }) {
      return {
        ...state,
        result: payload,
      };
    },
    getTocResult(state, { payload }) {
      return {
        ...state,
        tocResult: payload,
      };
    },
    getIterations(state, { payload }) {
      return {
        ...state,
        iterations: payload,
      };
    },
    modifySelectedControllers(state, { payload }) {
      return {
        ...state,
        selectedControllers: payload,
      };
    },
    modifySelectedResults(state, { payload }) {
      return {
        ...state,
        selectedResults: payload,
      };
    },
    modifyConfigCategories(state, { payload }) {
      return {
        ...state,
        iterationParams: payload,
      };
    },
    modifyConfigData(state, { payload }) {
      return {
        ...state,
        configData: payload,
      };
    },
  },
};
