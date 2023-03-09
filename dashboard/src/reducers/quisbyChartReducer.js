import * as TYPES from "../actions/types";

const initialState = {
  data: [],
  chartData: [],
  docLink: "",
};

const QuisbyChartReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.GET_QUISBY_DATA:
      return {
        ...state,
        data: payload,
      };
    case TYPES.SET_PARSED_DATA:
      return {
        ...state,
        chartData: payload,
      };
    case TYPES.SET_QUISBY_DOC_LINK:
      return {
        ...state,
        docLink: payload,
      };
    default:
      return state;
  }
};

export default QuisbyChartReducer;
