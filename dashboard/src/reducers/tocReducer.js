import * as TYPES from "../actions/types";

const initialState = {
  inventoryDownloadLink: "",
  drillMenuData: [],
  activeFile: {},
};

const TableOfContentReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.SET_INVENTORY_LINK: {
      return {
        ...state,
        inventoryDownloadLink: payload,
      };
    }
    case TYPES.SET_DRILL_MENU_DATA: {
      return { ...state, drillMenuData: payload };
    }
    case TYPES.SET_ACTIVE_FILE: {
      return { ...state, activeFile: payload };
    }
    default:
      return state;
  }
};
export default TableOfContentReducer;
