import {
  KEEP_USER_LOGGED_IN,
  USER_NOTION_ALERTS,
  SET_SIGNUP_BUTTON,
  SET_LOGIN_BUTTON,
  SET_LOGIN_DETAILS,
} from "../actions/types";

const initialState = {
  keepLoggedIn: false,
  alerts: [],
  isLoginBtnDisabled: true,
  isSignupBtnDisabled: true,
  passwordLength: 8,
  loginDetails: {},
};

const AuthReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case KEEP_USER_LOGGED_IN:
      return {
        ...state,
        keepLoggedIn: payload,
      };
    case USER_NOTION_ALERTS:
      return {
        ...state,
        alerts: [...payload],
      };
    case SET_LOGIN_BUTTON:
      return {
        ...state,
        isLoginBtnDisabled: payload,
      };
    case SET_SIGNUP_BUTTON:
      return {
        ...state,
        isSignupBtnDisabled: payload,
      };
    case SET_LOGIN_DETAILS:
      return {
        ...state,
        loginDetails: { ...payload },
      };
    default:
      return state;
  }
};

export default AuthReducer;
