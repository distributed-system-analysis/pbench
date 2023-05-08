import * as CONSTANTS from "assets/constants/browsingPageConstants";
import * as TYPES from "actions/types";

const initialState = {
  publicData: [],
  favoriteRepoNames: [],
  tableData: [],
  offset: CONSTANTS.START_OFFSET,
  limit: CONSTANTS.INITIAL_PAGE_LIMIT,
  perPage: CONSTANTS.DEFAULT_PER_PAGE,
  searchKey: "",
  filter: {
    startDate: "",
    endDate: "",
  },
};

const DatasetListReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.UPDATE_PUBLIC_DATASETS:
      return {
        ...state,
        publicData: [...payload],
      };
    case TYPES.FAVORITED_DATASETS:
      return {
        ...state,
        favoriteRepoNames: [...payload],
      };
    case TYPES.SET_PAGE_OFFSET:
      return {
        ...state,
        offset: payload,
      };
    case TYPES.SET_PAGE_LIMIT:
      return {
        ...state,
        limit: payload,
      };
    case TYPES.SET_DATE_RANGE:
      return {
        ...state,
        filter: payload,
      };
    case TYPES.SET_SEARCH_KEY:
      return {
        ...state,
        searchKey: payload,
      };
    case TYPES.SET_PER_PAGE:
      return {
        ...state,
        perPage: payload,
      };
    default:
      return state;
  }
};

export default DatasetListReducer;
