import {
  GET_PUBLIC_CONTROLLERS,
  FAVORITED_CONTROLLERS,
  UPDATE_PUBLIC_CONTROLLERS,
} from "../actions/types";

const initialState = {
  publicData: [],
  favoriteRepoNames: [],
  tableData: []
};

const PublicControllerReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case GET_PUBLIC_CONTROLLERS:
      return {
        ...state,
        publicData: [...payload],
        tableData: [...payload]
      };
    case FAVORITED_CONTROLLERS:
      return {
        ...state,
        favoriteRepoNames: [...payload],
      };
    case UPDATE_PUBLIC_CONTROLLERS:
      return {
        ...state,
        publicData: [...payload]
      }
    default:
      return state;
  }
};

export default PublicControllerReducer;
