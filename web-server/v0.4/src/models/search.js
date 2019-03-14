/* eslint-disable no-underscore-dangle */
import { queryIndexMapping, searchQuery } from '../services/search';

export default {
  namespace: 'search',

  state: {
    mapping: {},
    searchResults: [],
    fields: [],
  },

  effects: {
    *rehydrate({ payload }, { put }) {
      yield put({
        type: 'rehydrateSearch',
        payload,
      });
    },
    *fetchIndexMapping({ payload }, { call, put }) {
      const response = yield call(queryIndexMapping, payload);
      const { datastoreConfig, indices } = payload;

      const index = datastoreConfig.prefix + datastoreConfig.run_index + indices[0];
      const mapping = response[index].mappings['pbench-run'].properties;
      const fields = [];
      const filters = {};

      Object.entries(mapping).forEach(([key, value]) => {
        if (typeof value.properties !== 'undefined') {
          filters[key] = Object.keys(value.properties);
          fields.concat(Object.keys(value.properties));
        }
      });

      yield put({
        type: 'getIndexMapping',
        payload: filters,
      });
      yield put({
        type: 'getIndexFields',
        payload: fields,
      });
      yield put({
        type: 'global/modifySelectedFields',
        payload: ['run.name', 'run.config', 'run.controller', '@metadata.controller_dir'],
      });
    },
    *fetchSearchResults({ payload }, { call, put }) {
      const response = yield call(searchQuery, payload);
      const { selectedFields } = payload;

      const searchResults = {};
      searchResults.resultCount = response.hits.total;
      const parsedResults = [];

      response.hits.hits.forEach(result => {
        const parsedResult = {};

        selectedFields.forEach(field => {
          if (typeof result.fields[field] !== 'undefined') {
            const fieldValue = result.fields[field][0];
            parsedResult[field] = fieldValue;
          }
        });

        if (typeof result._id !== 'undefined') {
          parsedResult.key = result._id;
        }

        parsedResults.push(parsedResult);
      });

      searchResults.results = parsedResults;

      yield put({
        type: 'getSearchResults',
        payload: searchResults,
      });
    },
  },

  reducers: {
    rehydrateSearch(state, { payload }) {
      return {
        ...state,
        ...payload,
      };
    },
    getIndexMapping(state, { payload }) {
      return {
        ...state,
        mapping: payload,
      };
    },
    getIndexFields(state, { payload }) {
      return {
        ...state,
        fields: payload,
      };
    },
    getSearchResults(state, { payload }) {
      return {
        ...state,
        searchResults: payload,
      };
    },
  },
};
