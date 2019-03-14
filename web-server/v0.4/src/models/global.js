import { saveUserSession, queryUserSession } from '../services/global';

export default {
  namespace: 'global',

  state: {
    sessionBannerVisible: false,
    sessionDescription: '',
    sessionId: '',
    collapsed: false,
    selectedIndices: [],
    selectedResults: [],
    selectedControllers: [],
    selectedFields: [],
    selectedIterations: [],
  },

  effects: {
    *rehydrateSession({ payload }, { put }) {
      yield put({
        type: 'rehydrateGlobal',
        payload: payload.global,
      });
      yield put({
        type: 'dashboard/rehydrate',
        payload: payload.global,
      });
      yield put({
        type: 'search/rehydrate',
        payload: payload.global,
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
    *saveUserSession({ payload }, { call }) {
      const response = yield call(saveUserSession, payload);
      return response;
    },
    *fetchUserSession({ payload }, { call }) {
      const response = yield call(queryUserSession, payload);
      const { config } = response.data.url;
      const parsedSessionConfig = JSON.parse(config);
      return {
        sessionConfig: parsedSessionConfig,
        sessionMetadata: response.data.url,
      };
    },
  },

  reducers: {
    rehydrateGlobal(state, { payload }) {
      return {
        ...state,
        ...payload,
      };
    },
    changeLayoutCollapsed(state, { payload }) {
      return {
        ...state,
        collapsed: payload,
      };
    },
    startUserSession(state, { payload }) {
      return {
        ...state,
        sessionBannerVisible: payload.render,
        sessionDescription: payload.sessionDescription,
        sessionId: payload.sessionId,
      };
    },
    exitUserSession(state) {
      return {
        ...state,
        sessionBannerVisible: false,
        sessionDescription: '',
        sessionId: '',
      };
    },
    modifySelectedIndices(state, { payload }) {
      if (payload.type) {
        return {
          ...state,
          selectedIndices:
            state.selectedIndices.length === 0 ? payload.indices : state.selectedIndices,
        };
      }
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
    modifySelectedIterations(state, { payload }) {
      return {
        ...state,
        selectedIterations: payload,
      };
    },
  },
};
