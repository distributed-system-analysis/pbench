import { querySharedSessions, updateDescription, deleteSharedSessions } from '../services/explore';

export default {
  namespace: 'explore',

  state: {
    sharedSessions: [],
    loading: false,
  },

  effects: {
    *fetchSharedSessions({ payload }, { call, put }) {
      const response = yield call(querySharedSessions, payload);

      yield put({
        type: 'getSharedSessions',
        payload: response.data.urls,
      });
    },
    *editDescription({ payload }, { call }) {
      const response = yield call(updateDescription, payload);
      return response;
    },
    *deleteSharedSessions({ payload }, { call, put }) {
      const response = yield call(deleteSharedSessions, payload);

      yield put({
        type: 'getSharedSessions',
        payload: response.data.urls,
      });
    },
  },

  reducers: {
    getSharedSessions(state, { payload }) {
      return {
        ...state,
        sharedSessions: payload,
      };
    },
  },
};
