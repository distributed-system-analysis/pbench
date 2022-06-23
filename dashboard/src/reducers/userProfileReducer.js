import {
  GET_USER_DETAILS,
  UPDATE_USER_DETAILS,
  RESET_DATA,
  SET_USER_DETAILS,
} from "../actions/types";

const initialState = {
  userDetails: {},
  userDetails_copy: {},
  updatedUserDetails: {},
  isUserDetailsUpdated: false,
};

const UserProfileReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case GET_USER_DETAILS:
      return {
        ...state,
        userDetails: Object.assign({}, payload),
        userDetails_copy: Object.assign({}, payload),
      };
    case UPDATE_USER_DETAILS:
      return {
        ...state,
        userDetails: Object.assign({}, payload.userDetails),
        updatedUserDetails: Object.assign({}, payload.updatedUserDetails),
        isUserDetailsUpdated: true,
      };
    case RESET_DATA:
      return {
        ...state,
        isUserDetailsUpdated: false,
        updatedUserDetails: {},
      };
    case SET_USER_DETAILS:
      return {
        ...state,
        userDetails: Object.assign({}, payload),
      };
    default:
      return state;
  }
};

export default UserProfileReducer;
