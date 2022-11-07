import * as TYPES from "./types";

export const setActiveItem = (item) => {
  return {
    type: TYPES.SET_ACTIVE_MENU_ITEM,
    payload: item,
  };
};
