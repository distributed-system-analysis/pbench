import * as TYPES from "./types";
import API from "../utils/axiosInstance";

export const fetchTOC =
  (param, parent, callForSubData) => async (dispatch, getState) => {
    try {
      const endpoints = getState().apiEndpoint.endpoints;
      const response = await API.post(
        `${endpoints?.api?.datasets_contents}/${param}`,
        {
          parent: parent,
        }
      );
      if (response.status === 200 && response.data) {
        dispatch({
          type: callForSubData ? "GET_SUB_DIR_DATA" : "GET_TOC_DATA",
          payload: response.data,
        });
      }
    } catch (error) {
      return error;
    }
  };

export const updateTableData = (data) => {
  return {
    type: TYPES.UPDATE_TABLE_DATA,
    payload: data,
  };
};

export const updateSearchSpace = (data) => {
  return {
    type: TYPES.UPDATE_SEARCH_SPACE,
    payload: data,
  };
};

export const updateStack = (length) => {
  return {
    type: TYPES.UPDATE_STACK,
    payload: length,
  };
};

export const updateCurrData = (data) => {
  return {
    type: TYPES.UPDATE_CURR_DATA,
    payload: data,
  };
};

export const updateTOCLoader = (data) => {
  return {
    type: TYPES.UPDATE_TOC_LOADING,
    payload: data,
  };
};
