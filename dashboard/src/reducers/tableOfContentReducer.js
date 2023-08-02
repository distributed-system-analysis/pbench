import {
  GET_SUB_DIR_DATA,
  GET_TOC_DATA,
  UPDATE_CONTENT_DATA,
  UPDATE_CURR_DATA,
  UPDATE_SEARCH_SPACE,
  UPDATE_STACK,
  UPDATE_TABLE_DATA,
} from "actions/types";

const initialState = {
  stack: [],
  searchSpace: [],
  tableData: [],
  contentData: [],
  currData: [],
};

const TableOfContentReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case GET_TOC_DATA:
      return {
        ...state,
        stack: [payload],
        searchSpace: payload.files,
        tableData: payload.files,
        contentData: payload,
      };

    case GET_SUB_DIR_DATA:
      return {
        ...state,
        stack: [...state.stack, payload],
        searchSpace: payload.files,
        tableData: payload.files,
        contentData: payload,
        isLoading: false,
      };

    case UPDATE_TABLE_DATA:
      return {
        ...state,
        tableData: payload,
      };
    case UPDATE_CONTENT_DATA:
      return {
        ...state,
        contentData: payload,
      };
    case UPDATE_SEARCH_SPACE:
      return {
        ...state,
        searchSpace: payload,
      };

    case UPDATE_STACK:
      return {
        ...state,
        stack: state.stack.slice(0, payload),
      };

    case UPDATE_CURR_DATA:
      return {
        ...state,
        currData: payload,
      };
    default:
      return state;
  }
};
export default TableOfContentReducer;
