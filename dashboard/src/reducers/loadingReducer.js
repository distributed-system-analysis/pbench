import { COMPLETED, DASHBOARD_LOADING, LOADING } from "../actions/types";

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
    case DASHBOARD_LOADING:
      return {
        ...state,
        isLoading: false,
        isDashboardLoading: true,
      };
    case COMPLETED:
      return {
        ...state,
        isLoading: false,
        isDashboardLoading: false,
      };
    default:
      return state;
  }
};

export default LoadingReducer;
