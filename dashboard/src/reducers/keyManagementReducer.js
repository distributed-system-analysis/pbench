import * as TYPES from "actions/types";

const initialState = {
  keyList: [],
  isModalOpen: false,
  newKeyLabel: "",
};

const KeyManagementReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.SET_API_KEY_LIST:
      return {
        ...state,
        keyList: payload,
      };
    case TYPES.TOGGLE_NEW_KEY_MODAL:
      return {
        ...state,
        isModalOpen: payload,
      };
    case TYPES.SET_NEW_KEY_LABEL:
      return {
        ...state,
        newKeyLabel: payload,
      };
    default:
      return state;
  }
};

export default KeyManagementReducer;
