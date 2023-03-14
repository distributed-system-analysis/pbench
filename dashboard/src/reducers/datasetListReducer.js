import * as CONSTANTS from "assets/constants/browsingPageConstants";
import * as TYPES from "actions/types";

const initialState = {
  publicData: [],
  favoriteRepoNames: [],
  tableData: [],
  offset: 0,
  limit: CONSTANTS.LIMIT,
  perPage: CONSTANTS.DEFAULT_PER_PAGE,
  totalDatasets: 0,
  searchKey: "",
  filter: {
    startDate: "",
    endDate: "",
  },
};

const DatasetListReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.GET_PUBLIC_DATASETS:
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
    case TYPES.SET_TOTAL_DATASETS:
      return {
        ...state,
        totalDatasets: payload,
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
