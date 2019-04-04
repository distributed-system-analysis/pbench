import {
  queryControllers,
  queryResults,
  queryResult,
  queryTocResult,
  queryIterations,
} from '../services/dashboard';

import { parseIterationData } from '../utils/parse';

export default {
  namespace: 'dashboard',

  state: {
    result: [],
    results: [],
    configCategories: [],
    configData: [],
    iterations: {
      responseData: [],
      configData: {},
    },
    controllers: [],
    tocResult: [],
    loading: false,
  },

  effects: {
    *fetchControllers({ payload }, { call, put }) {
      let response = yield call(queryControllers, payload);

      let controllers = [];
      response.aggregations.controllers.buckets.map(controller => {
        let last_mod_val;
        let last_mod_str;
        if (controller.runs.value != null) {
          // Look for v1 data
          last_mod_val = controller.runs.value;
          last_mod_str = controller.runs.value_as_string;
        } else {
          // Fall back to pre-v1 data
          last_mod_val = controller.runs_preV1.value;
          last_mod_str = controller.runs_preV1.value_as_string;
        }
        controllers.push({
          key: controller.key,
          controller: controller.key,
          results: controller.doc_count,
          last_modified_value: last_mod_val,
          last_modified_string: last_mod_str,
        });
      });

      yield put({
        type: 'getControllers',
        payload: controllers,
      });
    },
    *fetchResults({ payload }, { call, put }) {
      let response = yield call(queryResults, payload);
      let results = [];
      let hits;
      try {
        hits = response.hits.hits;
      } catch (error) {
        console.log('Unsuccessful run data query, no hits on matching documents: ' + error);
        hits = [];
      }
      hits.map((result, index) => {
        let name, controller, id, start, end;
        try {
          name = result.fields['run.name'][0];
          controller = result.fields['run.controller'][0];
          id = result.fields['run.id'][0];
          start =
            typeof result.fields['run.start'] != 'undefined'
              ? result.fields['run.start'][0]
              : result.fields['run.start_run'][0];
          end =
            typeof result.fields['run.end'] != 'undefined'
              ? result.fields['run.end'][0]
              : result.fields['run.end_run'][0];
        } catch (error) {
          console.log(
            "Problem handling 'run' documents (most likely missing required 'run' field name): " +
              error
          );
          return;
        }
        let record = {
          key: index,
          startUnixTimestamp: Date.parse(start),
          ['run.name']: name,
          ['run.controller']: controller,
          ['run.start']: start,
          ['run.end']: end,
          ['id']: id,
        };
        if (typeof result.fields['run.config'] != 'undefined') {
          record['run.config'] = result.fields['run.config'][0];
        }
        if (typeof result.fields['run.prefix'] != 'undefined') {
          record['run.prefix'] = result.fields['run.prefix'][0];
        }
        if (typeof result.fields['@metadata.controller_dir'] != 'undefined') {
          record['@metadata.controller_dir'] = result.fields['@metadata.controller_dir'][0];
        }
        if (typeof result.fields['@metadata.satellite'] != 'undefined') {
          record['@metadata.satellite'] = result.fields['@metadata.satellite'][0];
        }
        results.push(record);
      });

      yield put({
        type: 'getResults',
        payload: results,
      });
    },
    *fetchResult({ payload }, { call, put }) {
      let response = yield call(queryResult, payload);

      let result = typeof response.hits.hits[0] !== 'undefined' ? response.hits.hits[0] : [];

      yield put({
        type: 'getResult',
        payload: result,
      });
    },
    *fetchTocResult({ payload }, { call, put }) {
      let response = yield call(queryTocResult, payload);

      let tocResult = [];
      response.hits.hits.map(result => {
        // tocResult.push(result._source.directory);
        if (result._source.files != undefined) {
          result._source.files.map(path => {
            let url = result._source.directory + path.name;
            tocResult[url] = [path.size, path.mode];
          });
        }
      });

      yield put({
        type: 'getTocResult',
        payload: tocResult,
      });
    },
    *fetchIterations({ payload }, { call, put }) {
      let response = yield call(queryIterations, payload);

      const parsedIterationData = parseIterationData(response);

      yield put({
        type: 'getIterations',
        payload: parsedIterationData,
      });
    },
    *updateConfigCategories({ payload }, { select, put }) {
      yield put({
        type: 'modifyConfigCategories',
        payload: payload,
      });
    },
    *updateConfigData({ payload }, { select, put }) {
      yield put({
        type: 'modifyConfigData',
        payload: payload,
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
        results: payload,
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
        configCategories: payload,
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
