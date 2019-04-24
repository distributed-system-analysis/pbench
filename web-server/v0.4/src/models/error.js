import { routerRedux } from 'dva/router';
import query from '../services/error';

export default {
  namespace: 'error',

  state: {
    error: '',
    isloading: false,
  },

  effects: {
    *query({ payload }, { call, put }) {
      yield call(query, payload.code);
      // redirect on client when network broken
      yield put(routerRedux.push(`/exception/${payload.code}`));
      yield put({
        type: 'trigger',
        payload: payload.code,
      });
    },
  },

  reducers: {
    trigger(state, action) {
      return {
        error: action.payload,
      };
    },
  },
};
