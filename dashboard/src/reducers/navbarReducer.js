import { NAVBAR_CLOSE, NAVBAR_OPEN } from "../actions/types";

const initialState = {
  isNavOpen: false,
};
const NavbarReducer = (state = initialState, action = {}) => {
  const { type } = action;
  switch (type) {
    case NAVBAR_OPEN:
      return {
        ...state,
        isNavOpen: true,
      };

    case NAVBAR_CLOSE:
      return {
        ...state,
        isNavOpen: false,
      };

    default:
      return state;
  }
};

export default NavbarReducer;
