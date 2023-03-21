import { SET_ENDPOINTS, SET_KEYCLOAK } from "../actions/types";

const initialState = {
  endpoints: {},
  keycloak: null,
};

const EndpointReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  if (type === SET_ENDPOINTS) {
    return {
      ...state,
      endpoints: payload,
    };
  }
  if (type === SET_KEYCLOAK) {
    return {
      ...state,
      keycloak: payload,
    };
  }
  return state;
};

export default EndpointReducer;
