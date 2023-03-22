import {
  GET_PUBLIC_DATASETS,
  FAVORITED_DATASETS,
  UPDATE_PUBLIC_DATASETS,
} from "../actions/types";

const initialState = {
  publicData: [],
  favoriteRepoNames: [],
  tableData: [],
};

const DatasetListReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case GET_PUBLIC_DATASETS:
      return {
        ...state,
        publicData: [...payload],
        tableData: [...payload],
      };
    case FAVORITED_DATASETS:
      return {
        ...state,
        favoriteRepoNames: [...payload],
      };
    case UPDATE_PUBLIC_DATASETS:
      return {
        ...state,
        publicData: [...payload],
      };
    default:
      return state;
  }
};

export default DatasetListReducer;
