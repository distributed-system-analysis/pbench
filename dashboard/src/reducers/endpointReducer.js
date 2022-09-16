import { SET_ENDPOINTS } from "../actions/types";

const initialState = {
  endpoints: {},
};

const EndpointReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  if (type === SET_ENDPOINTS) {
    return {
      ...state,
      endpoints: payload,
    };
  }
  return state;
};

export default EndpointReducer;
