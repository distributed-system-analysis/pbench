import * as TYPES from "./types";
import API from "../utils/axiosInstance";
import { uriTemplate } from "../utils/helper";
import { showToast } from "./toastActions";
import { DANGER } from "assets/constants/toastConstants";

export const fetchTOC =
  (param, parent, callForSubData) => async (dispatch, getState) => {
    try {
      const endpoints = getState().apiEndpoint.endpoints;
      const uri = uriTemplate(endpoints, "datasets_contents", {
        dataset: param,
        target: parent,
      });
      const response = await API.get(uri);
      if (response.status === 200 && response.data) {
        dispatch({
          type: callForSubData ? "GET_SUB_DIR_DATA" : "GET_TOC_DATA",
          payload: response.data,
        });
      }
    } catch (error) {
      const msg = error.response?.data?.message;
      dispatch(showToast(DANGER, msg ? msg : `Error response: ERROR_MSG`));
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
