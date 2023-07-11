import * as TYPES from "../actions/types";

const initialState = {
  data: [],
  chartData: [],
  activeResourceId: "",
  unsupportedType: "",
};

const ComparisonReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.SET_QUISBY_DATA:
      return {
        ...state,
        data: payload,
      };
    case TYPES.SET_PARSED_DATA:
      return {
        ...state,
        chartData: payload,
      };
    case TYPES.SET_ACTIVE_RESOURCEID:
      return {
        ...state,
        activeResourceId: payload,
      };
    case TYPES.IS_UNSUPPORTED_TYPE:
      return {
        ...state,
        unsupportedType: payload,
      };
    default:
      return state;
  }
};

export default ComparisonReducer;
