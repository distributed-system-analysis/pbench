export default {
  namespace: 'global',

  state: {
    collapsed: false,
    selectedIndices: [],
    selectedResults: [],
    selectedControllers: [],
    selectedFields: [],
    selectedIterations: [],
  },

  effects: {
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
