import * as TYPES from "./types";
import API from "../utils/axiosInstance";

export const fetchTOC =
  (param, parent, callForSubData) => async (dispatch, getState) => {
    try {
      const endpoints = getState().apiEndpoint.endpoints;
      console.log(endpoints);
      const response = await API.post(
        `${endpoints?.api?.datasets_contents}/${param}`,
        {
          parent: parent,
        }
      );
      if (response.status === 200 && response.data && !callForSubData) {
        dispatch({
          type: "GET_TOC_DATA",
          payload: response?.data,
        });
      } else if (response.status === 200 && response.data && callForSubData) {
        dispatch({
          type: "GET_SUB_DIR_DATA",
          payload: response?.data,
        });
      }
    } catch (error) {
      return error;
    }
  };

export const updateTableData = (data) => async (dispatch) => {
  dispatch({
    type: TYPES.UPDATE_TABLE_DATA,
    payload: data,
  });
};

export const updateSearchSpace = (data) => async (dispatch) => {
  dispatch({
    type: TYPES.UPDATE_SEARCH_SPACE,
    payload: data,
  });
};

export const updateStack = (data) => async (dispatch) => {
  dispatch({
    type: TYPES.UPDATE_STACK,
    payload: data,
  });
};

export const updateCurrData = (data) => async (dispatch) => {
  dispatch({
    type: TYPES.UPDATE_CURR_DATA,
    payload: data,
  });
};
export const updateTOCLoader = (data) => async (dispatch) => {
  dispatch({
    type: TYPES.UPDATE_TOC_LOADING,
    payload: data,
  });
};
