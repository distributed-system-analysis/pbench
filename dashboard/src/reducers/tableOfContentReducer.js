import {
  GET_SUB_DIR_DATA,
  GET_TOC_DATA,
  UPDATE_CURR_DATA,
  UPDATE_SEARCH_SPACE,
  UPDATE_STACK,
  UPDATE_TABLE_DATA,
  UPDATE_TOC_LOADING,
} from "actions/types";

const initialState = {
  stack: [],
  searchSpace: [],
  tableData: [],
  contentData: [],
  currData: [],
  isLoading: true,
};

const TableOfContentReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case GET_TOC_DATA:
    case GET_SUB_DIR_DATA:
      return {
        ...state,
        stack: type === GET_TOC_DATA ? [payload] : [...state.stack, payload],
        searchSpace: payload.files,
        tableData: payload.files,
        currData: type === GET_TOC_DATA ? state.currData : payload,
        isLoading: false,
        contentData: type === GET_TOC_DATA ? payload : state.contentData,
      };

    case UPDATE_TABLE_DATA:
      return {
        ...state,
        tableData: payload,
      };

    case UPDATE_SEARCH_SPACE:
      return {
        ...state,
        searchSpace: payload,
      };

    case UPDATE_STACK:
      const newState = { ...state };
      newState.stack.length = payload;
      return newState;

    case UPDATE_CURR_DATA:
      return {
        ...state,
        currData: payload,
      };

    case UPDATE_TOC_LOADING:
      return {
        ...state,
        isLoading: payload,
      };
    default:
      return state;
  }
};
export default TableOfContentReducer;
