export default {
  namespace: 'user',

  state: {
    favoriteControllers: [],
    favoriteResults: [],
  },

  effects: {
    *favoriteController({ payload }, { put }) {
      yield put({
        type: 'modifyFavoritedControllers',
        payload,
      });
    },
    *favoriteResult({ payload }, { put }) {
      yield put({
        type: 'modifyFavoritedResults',
        payload,
      });
    },
  },

  reducers: {
    modifyFavoritedControllers(state, { payload }) {
      return {
        ...state,
        favoriteControllers: [...state.favoriteControllers, payload],
      };
    },
    modifyFavoritedResults(state, { payload }) {
      return {
        ...state,
        favoriteResults: [...state.favoriteResults, payload],
      };
    },
  },
};
