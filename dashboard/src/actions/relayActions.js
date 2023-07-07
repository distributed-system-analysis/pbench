import * as TYPES from "./types";

import { DANGER, ERROR_MSG, SUCCESS } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import { getDatasets } from "./overviewActions";
import { showToast } from "./toastActions";
import { uriTemplate } from "../utils/helper";

export const uploadFile = (fileURI) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;

    const uri = uriTemplate(endpoints, "relay", {
      uri: fileURI,
    });
    const response = await API.post(uri, null, null);
    if (response.status >= 200 && response.status < 300) {
      dispatch(showToast(SUCCESS, response.data.message));
      dispatch(toggleRelayModal(false));
      dispatch(handleInputChange(""));
      if (response.status === 201) {
        // need to remove once response returns the uploaded dataset
        dispatch(getDatasets());
      }
    }
  } catch (error) {
    const toastMessage = error.response
      ? error.response.data.message
      : ERROR_MSG;
    dispatch(showToast(DANGER, toastMessage));
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};
export const toggleRelayModal = (isOpen) => ({
  type: TYPES.TOGGLE_RELAY_MODAL,
  payload: isOpen,
});

export const handleInputChange = (value) => ({
  type: TYPES.SET_RELAY_DATA,
  payload: value,
});
