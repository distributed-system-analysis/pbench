import * as TYPES from "./types";

import API from "../utils/axiosInstance";
import { DANGER } from "assets/constants/toastConstants";
import { showToast } from "./toastActions";
import { uriTemplate } from "../utils/helper";

export const fetchTOC =
  (param, dataUri, callForSubData) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      const endpoints = getState().apiEndpoint.endpoints;
      const parent = dataUri?.split("contents/").pop();
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
      dispatch(showToast(DANGER, msg ?? `Error response: ${error}`));
    }
    dispatch({ type: TYPES.COMPLETED });
  };

export const updateTableData = (data) => ({
  type: TYPES.UPDATE_TABLE_DATA,
  payload: data,
});

export const updateContentData = (data) => ({
  type: TYPES.UPDATE_CONTENT_DATA,
  payload: data,
});

export const updateSearchSpace = (data) => ({
  type: TYPES.UPDATE_SEARCH_SPACE,
  payload: data,
});

export const updateStack = (length) => ({
  type: TYPES.UPDATE_STACK,
  payload: length,
});

export const updateCurrData = (data) => ({
  type: TYPES.UPDATE_CURR_DATA,
  payload: data,
});
