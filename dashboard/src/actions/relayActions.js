import * as TYPES from "./types";

import { DANGER, SUCCESS } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import { getDatasets } from "./overviewActions";
import { showToast } from "./toastActions";
import { uriTemplate } from "../utils/helper";

export const uploadFile = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const fileURI = getState().overview.relayInput;
    const uri = uriTemplate(endpoints, "relay", { uri: fileURI });
    const response = await API.post(uri, null, null);
    if (response.status >= 200 && response.status < 300) {
      dispatch(showToast(SUCCESS, response.data.message));
      dispatch(setRelayModalState(false));
      dispatch(handleInputChange(""));
      if (response.status === 201) {
        // need to remove once response returns the uploaded dataset
        dispatch(getDatasets());
      }
    }
  } catch (error) {
    dispatch(
      showToast(DANGER, error?.response?.data?.message ?? `Error: ${error}`)
    );
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};
export const setRelayModalState = (isOpen) => ({
  type: TYPES.TOGGLE_RELAY_MODAL,
  payload: isOpen,
});

export const handleInputChange = (value) => ({
  type: TYPES.SET_RELAY_DATA,
  payload: value,
});
