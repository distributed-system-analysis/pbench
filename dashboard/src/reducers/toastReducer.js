import { SHOW_TOAST, CLEAR_TOAST } from "../actions/types";
import { uid } from "../utils/helper";

const initialState = {
  alerts: [],
};

const ToastReducer = (state = initialState, action = {}) => {
  const { type } = action;
  switch (type) {
    case SHOW_TOAST:
      return {
        ...state,
        alerts: setValue(state.alerts, action),
      };
    case CLEAR_TOAST:
      return {
        alerts: setValue(state.alerts, action),
      };
    default:
      return state;
  }
};

function setValue(state, action) {
  const { type, payload } = action;
  switch (type) {
    case SHOW_TOAST: {
      let obj = {
        variant: payload.variant,
        title: payload.title,
        message: payload?.message,
        key: uid(),
      };
      state.push(obj);
      return state;
    }
    case CLEAR_TOAST: {
      let activeAlert = state.filter((item) => item.key !== payload);
      state = [...activeAlert];
      return state;
    }
    default:
      return state;
  }
}

export default ToastReducer;
