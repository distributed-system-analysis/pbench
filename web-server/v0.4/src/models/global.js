import { queryDatastoreConfig, queryMonthIndices } from '../services/global';

export default {
  namespace: 'global',

  state: {
    collapsed: false,
    datastoreConfig: {},
    indices: [],
    selectedIndices: [],
    selectedResults: [],
    selectedControllers: [],
    selectedFields: [],
    selectedIterationKeys: [],
    selectedIterations: [],
  },

  effects: {
    *fetchDatastoreConfig({ payload }, { call, put }) {
      const response = yield call(queryDatastoreConfig, payload);

      // Remove the trailing slashes if present, we'll take care of adding
      // them back in the proper context.
      response.elasticsearch = response.elasticsearch.replace(/\/+$/, '');
      response.results = response.results.replace(/\/+$/, '');

      yield put({
        type: 'getDatastoreConfig',
        payload: response,
      });
    },
    *fetchMonthIndices({ payload }, { call, put }) {
      const response = yield call(queryMonthIndices, payload);
      const { datastoreConfig } = payload;
      const indices = [];

      const prefix = datastoreConfig.prefix + datastoreConfig.run_index.slice(0, -1);
      response.forEach(index => {
        if (index.index.includes(prefix)) {
          indices.push(index.index.split('.').pop());
        }
      });

      indices.sort((a, b) => parseInt(b.replace('-', ''), 10) - parseInt(a.replace('-', ''), 10));

      yield put({
        type: 'getMonthIndices',
        payload: indices,
      });
    },
    *updateSelectedIndices({ payload }, { put }) {
      yield put({
        type: 'modifySelectedIndices',
        payload,
      });
    },
    *updateSelectedControllers({ payload }, { put }) {
      yield put({
        type: 'modifySelectedControllers',
        payload,
      });
    },
    *updateSelectedResults({ payload }, { put }) {
      yield put({
        type: 'modifySelectedResults',
        payload,
      });
    },
    *updateSelectedFields({ payload }, { put }) {
      yield put({
        type: 'modifySelectedFields',
        payload,
      });
    },
    *updateSelectedIterations({ payload }, { put }) {
      yield put({
        type: 'modifySelectedIterations',
        payload,
      });
    },
  },

  reducers: {
    changeLayoutCollapsed(state, { payload }) {
      return {
        ...state,
        collapsed: payload,
      };
    },
    getDatastoreConfig(state, { payload }) {
      return {
        ...state,
        datastoreConfig: payload,
      };
    },
    getMonthIndices(state, { payload }) {
      return {
        ...state,
        selectedIndices: [payload[0]],
        indices: payload,
      };
    },
    modifySelectedIndices(state, { payload }) {
      return {
        ...state,
        selectedIndices: payload,
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
    modifySelectedFields(state, { payload }) {
      return {
        ...state,
        selectedFields: payload,
      };
    },
    modifySelectedIterationKeys(state, { payload }) {
      return {
        ...state,
        selectedIterationKeys: payload,
      };
    },
    modifySelectedIterations(state, { payload }) {
      return {
        ...state,
        selectedIterations: payload,
      };
    },
  },
};
