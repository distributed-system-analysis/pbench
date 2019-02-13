import {
  queryControllers,
  queryResults,
  queryResult,
  queryTocResult,
  queryIterations,
} from '../services/dashboard';

export default {
  namespace: 'dashboard',

  state: {
    controller: '',
    result: [],
    results: [],
    configCategories: [],
    configData: [],
    iterations: [],
    controllers: [],
    selectedResults: [],
    tocResult: [],
    selectedController: '',
    loading: false,
  },

  effects: {
    *fetchControllers({ payload }, { call, put }) {
      let response = yield call(queryControllers, payload);

      let controllers = [];
      response.aggregations.controllers.buckets.map(controller => {
        controllers.push({
          key: controller.key,
          controller: controller.key,
          results: controller.doc_count,
          last_modified_value: controller.runs.value,
          last_modified_string: controller.runs.value_as_string,
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
      response.hits.hits.map(result => {
        results.push({
          key: result.fields['run.name'][0],
          ['run.name']: result.fields['run.name'][0],
          ['run.config']: result.fields['run.config'][0],
          ['run.prefix']:
            typeof result.fields['run.prefix'] !== 'undefined'
              ? result.fields['run.prefix'][0]
              : null,
          startRunUnixTimestamp: Date.parse(result.fields['run.start_run'][0]),
          ['run.startRun']: result.fields['run.start_run'][0],
          ['run.endRun']: result.fields['run.end_run'][0],
          ['id']: result.fields['@metadata.md5'][0],
        });
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
        tocResult.push(result._source.directory);
      });

      yield put({
        type: 'getTocResult',
        payload: tocResult,
      });
    },
    *fetchIterations({ payload }, { call, put }) {
      let response = yield call(queryIterations, payload);

      let iterations = [];
      response.map((iteration, index) => {
        iterations.push({
          iterationData: iteration.data,
          controllerName: iteration.config.url.split('/')[4],
          resultName: iteration.config.url.split('/')[5],
          tableId: index,
        });
      });

      yield put({
        type: 'getIterations',
        payload: iterations,
      });
    },
    *updateSelectedController({ payload }, { select, put }) {
      yield put({
        type: 'modifySelectedController',
        payload: payload,
      });
    },
    *updateSelectedResults({ payload }, { select, put }) {
      yield put({
        type: 'modifySelectedResults',
        payload: payload,
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
    modifySelectedController(state, { payload }) {
      return {
        ...state,
        selectedController: payload,
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
