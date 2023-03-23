import { USER_NOTION_ALERTS } from "../actions/types";

const initialState = {
  alerts: [],
};

const AuthReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case USER_NOTION_ALERTS:
      return {
        ...state,
        alerts: [...payload],
      };
    default:
      return state;
  }
};

export default AuthReducer;
