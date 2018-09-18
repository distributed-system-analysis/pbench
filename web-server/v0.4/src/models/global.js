import { queryDatastoreConfig } from '../services/global';

export default {
  namespace: 'global',

  state: {
    collapsed: true,
    datastoreConfig: {},
  },

  effects: {
    *fetchDatastoreConfig({ payload }, { call, put }) {
      let response = yield call(queryDatastoreConfig, payload);

      yield put({
        type: 'getDatastoreConfig',
        payload: response,
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
  },
};
