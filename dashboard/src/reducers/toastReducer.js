import { CLEAR_TOAST, SHOW_TOAST } from "actions/types";

const initialState = {
  alerts: [],
};

const ToastReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case SHOW_TOAST:
      return {
        ...state,
        alerts: payload,
      };
    case CLEAR_TOAST:
      return {
        alerts: payload,
      };
    default:
      return state;
  }
};

export default ToastReducer;
