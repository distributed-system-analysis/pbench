import { queryDatastoreConfig, queryMonthIndices } from '../services/global';

export default {
  namespace: 'global',

  state: {
    collapsed: false,
    datastoreConfig: {},
    indices: [],
    selectedIndices: [],
    selectorIndices: ['0'],
  },

  effects: {
    *fetchDatastoreConfig({ payload }, { call, put }) {
      let response = yield call(queryDatastoreConfig, payload);

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
      let response = yield call(queryMonthIndices, payload);

      let indices = [];
      const { datastoreConfig } = payload;
      let prefix = datastoreConfig.prefix + datastoreConfig.run_index.slice(0, -1);
      response.map(index => {
        if (index.index.includes(prefix)) {
          indices.push(index.index.split('.').pop());
        }
      });

      indices.sort((a, b) => {
        return parseInt(b.replace('-', '')) - parseInt(a.replace('-', ''));
      });

      yield put({
        type: 'getMonthIndices',
        payload: indices,
      });
    },
    *updateSelectedIndices({ payload }, { put }) {
      yield put({
        type: 'modifySelectedIndices',
        payload: payload,
      });
    },
    *updateSelectorIndices({ payload }, { put }) {
      yield put({
        type: 'modifySelectorIndices',
        payload: payload,
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
        indices: payload,
      };
    },
    modifySelectedIndices(state, { payload }) {
      return {
        ...state,
        selectedIndices: payload,
      };
    },
    modifySelectorIndices(state, { payload }) {
      return {
        ...state,
        selectorIndices: payload,
      };
    },
  },
};
