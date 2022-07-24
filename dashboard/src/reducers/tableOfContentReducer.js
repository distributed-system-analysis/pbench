import { UPDATE_SEARCH_SPACE } from "actions/types";
import { UPDATE_CURR_DATA } from "actions/types";
import { UPDATE_TOC_LOADING } from "actions/types";
import { UPDATE_STACK } from "actions/types";
import { UPDATE_TABLE_DATA } from "actions/types";
import { GET_SUB_DIR_DATA } from "actions/types";

import { GET_TOC_DATA } from "actions/types";

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
      return {
        ...state,
        stack: [payload],
        searchSpace: payload.files,
        tableData: payload.files,
        contentData: payload,
        isLoading: false,
      };

    case GET_SUB_DIR_DATA:
      return {
        ...state,
        stack: [...state.stack, payload],
        searchSpace: payload.files,
        tableData: payload.files,
        currData: payload,
        isLoading: false,
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
      return {
        ...state,
        stack: payload,
      };

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
