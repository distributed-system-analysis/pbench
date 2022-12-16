import { COMPLETED, LOADING } from "../actions/types";

const initialState = {
  isLoading: false,
};

const LoadingReducer = (state = initialState, action = {}) => {
  const { type } = action;
  switch (type) {
    case LOADING:
      return {
        ...state,
        isLoading: true,
      };

    case COMPLETED:
      return {
        ...state,
        isLoading: false,
      };
    default:
      return state;
  }
};

export default LoadingReducer;
