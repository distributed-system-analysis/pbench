import * as TYPES from "../actions/types";

const initialState = {
  datasets: [],
  savedRuns: [],
  newRuns: [],
  defaultPerPage: 5,
  initNewRuns: [],
  selectedRuns: [],
  expiringRuns: [],
};

const OverviewReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.USER_RUNS:
      return {
        ...state,
        datasets: payload,
      };
    case TYPES.SAVED_RUNS:
      return {
        ...state,
        savedRuns: payload,
      };
    case TYPES.NEW_RUNS:
      return {
        ...state,
        newRuns: payload,
      };
    case TYPES.INIT_NEW_RUNS:
      return {
        ...state,
        initNewRuns: payload,
      };
    case TYPES.SELECTED_NEW_RUNS:
      return {
        ...state,
        selectedRuns: payload,
      };
    case TYPES.EXPIRING_RUNS:
      return {
        ...state,
        expiringRuns: payload,
      };
    default:
      return state;
  }
};

export default OverviewReducer;
