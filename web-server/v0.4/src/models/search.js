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
        payload: ['run.name', 'run.config', 'run.controller'],
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
          parsedResult[field] = result._source[field.split('.')[0]][field.split('.')[1]];
        });

        if (typeof result._source.run.prefix !== 'undefined') {
          parsedResult['run.prefix'] = result._source.run.prefix;
        }
        if (typeof result._source.run.id !== 'undefined') {
          parsedResult.key = result._source.run.id;
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
