import { SET_ACTIVE_MENU_ITEM } from "../actions/types";

const initialState = {
  activeMenuItem: "overview",
};
const SidebarReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case SET_ACTIVE_MENU_ITEM:
      return {
        ...state,
        activeMenuItem: payload,
      };

    default:
      return state;
  }
};

export default SidebarReducer;
