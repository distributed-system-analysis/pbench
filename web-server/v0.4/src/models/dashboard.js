import {
  queryMonthIndices,
  queryControllers,
  queryResults,
  queryResult,
  queryIterations,
} from '../services/dashboard';

import moment from 'moment';

const defaultMonth = moment().toString();

export default {
  namespace: 'dashboard',

  state: {
    controller: '',
    indices: [],
    result: [],
    results: [],
    configCategories: [],
    configData: [],
    iterations: [],
    controllers: [],
    selectedResults: [],
    selectedController: '',
    startMonth: defaultMonth,
    endMonth: defaultMonth,
    loading: false,
  },

  effects: {
    *fetchHosts({ payload }, { call, put }) {
      let response = yield call(queryControllers, payload);

      let hosts = [];
      response.aggregations.run_hosts.buckets.map(host => {
        hosts.push({
          key: host.key,
          controller: host.key,
          results: host.doc_countå,
        });
      });

      yield put({
        type: 'getControllers',
        payload: hosts,
      });
    },
    *fetchResults({ payload }, { call, put }) {
      let response = yield call(queryResults, payload);

      let results = [];
      response.hits.hits.map(result => {
        results.push({
          key: result._source.run.id,
          result: result._source.run.id,
          config: Object.values(result._source.run.bench).join(" "), 
        });
      });

      yield put({
        type: 'getResults',
        payload: results,
      });
    },
    *fetchResult({ payload }, { call, put }) {
      let response = yield call(queryResult, payload);

      yield put({
        type: 'getResult',
        payload: [response.hits.hits[0]],
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
    getMonthIndices(state, { payload }) {
      return {
        ...state,
        indices: payload,
      };
    },
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
    getIterations(state, { payload }) {
      return {
        ...state,
        iterations: payload,
      };
    },
    modifyControllerStartMonth(state, action) {
      return {
        ...state,
        startMonth: action.payload,
      };
    },
    modifyControllerEndMonth(state, action) {
      return {
        ...state,
        endMonth: action.payload,
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