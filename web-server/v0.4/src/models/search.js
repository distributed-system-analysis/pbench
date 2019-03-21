import { queryIndexMapping, searchQuery } from '../services/search';

export default {
  namespace: 'search',

  state: {
    mapping: {},
    searchResults: [],
    fields: [],
    selectedFields: [],
    loading: false,
  },

  effects: {
    *fetchIndexMapping({ payload }, { call, put }) {
      let response = yield call(queryIndexMapping, payload);
      const { datastoreConfig, indices } = payload;

      let index = datastoreConfig.prefix + datastoreConfig.run_index + indices[0];
      let mapping = response[index].mappings['pbench-run'].properties;
      let fields = [];
      let filters = {};

      for (const [key, value] of Object.entries(mapping)) {
        if (typeof value.properties !== 'undefined') {
          filters[key] = Object.keys(value.properties);
          fields.concat(Object.keys(value.properties));
        }
      }

      yield put({
        type: 'getIndexMapping',
        payload: filters,
      });
      yield put({
        type: 'getIndexFields',
        payload: fields,
      });
      yield put({
        type: 'modifySelectedFields',
        payload: ['run.name', 'run.config', 'run.controller'],
      });
      yield put({
        type: 'modifySelectedIndices',
        payload: [indices[0]],
      });
    },
    *fetchSearchResults({ payload }, { call, put }) {
      try {
        let response = yield call(searchQuery, payload);
        let { selectedFields } = payload;

        let searchResults = {};
        searchResults['resultCount'] = response.hits.total;
        let parsedResults = [];
        response.hits.hits.map((result) => {
          let parsedResult = {};
          selectedFields.map(field => {
            parsedResult[field] = result._source[field.split('.')[0]][field.split('.')[1]];
          });
          if (typeof result._source['run']['prefix'] != 'undefined') {
            parsedResult['run.prefix'] = result._source['run']['prefix'];
          }
          if (typeof result._source['run']['id'] !== 'undefined') {
            parsedResult['key'] = result._source['run']['id'];
          }
          parsedResults.push(parsedResult);
        });
        searchResults['results'] = parsedResults;

        yield put({
          type: 'getSearchResults',
          payload: searchResults,
        });
      } catch (e) {
        console.log(e.message);
      }
    },
    *updateSelectedFields({ payload }, { select, put }) {
      yield put({
        type: 'modifySelectedFields',
        payload: payload,
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
    modifySelectedFields(state, { payload }) {
      return {
        ...state,
        selectedFields: payload,
      };
    },
  },
};
