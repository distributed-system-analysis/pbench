import * as TYPES from "./types";

import { DANGER, SUCCESS } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import { showToast } from "./toastActions";
import { uriTemplate } from "../utils/helper";

export const sendFileRequest = (fileURI) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;

    const uri = uriTemplate(endpoints, "relay", {
      uri: fileURI,
    });
    const response = await API.post(uri, null, null);
    if (response.statusText === "OK") {
      dispatch(showToast(SUCCESS, response.json.message));
    }
  } catch (error) {
    dispatch(showToast(DANGER, error.response.data.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};
