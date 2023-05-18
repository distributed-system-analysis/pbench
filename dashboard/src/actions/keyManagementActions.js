import * as TYPES from "actions/types";

import { DANGER, ERROR_MSG, SUCCESS } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import { showToast } from "./toastActions";
import { uriTemplate } from "utils/helper";

export const getAPIkeysList = async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });

    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.get(uriTemplate(endpoints, "key", { key: "" }));

    if (response.status === 200) {
      dispatch({
        type: TYPES.SET_API_KEY_LIST,
        payload: response.data,
      });
    } else {
      dispatch(showToast(DANGER, ERROR_MSG));
    }
  } catch (error) {
    dispatch(showToast(DANGER, error));
  }
  dispatch({ type: TYPES.COMPLETED });
};

export const deleteAPIKey = (id) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.delete(
      uriTemplate(endpoints, "key", { key: id })
    );

    if (response.status === 200) {
      dispatch({
        type: TYPES.SET_API_KEY_LIST,
        payload: getState().keyManagement.keyList.filter(
          (item) => item.id !== id
        ),
      });

      const message = response.data ?? "Deleted";
      const toastMsg = message?.charAt(0).toUpperCase() + message?.slice(1);

      dispatch(showToast(SUCCESS, toastMsg));
    } else {
      dispatch(showToast(DANGER, ERROR_MSG));
    }
  } catch (error) {
    dispatch(showToast(DANGER, error));
  }
  dispatch({ type: TYPES.COMPLETED });
};

export const sendNewKeyRequest = (label) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const keyList = [...getState().keyManagement.keyList];

    const response = await API.post(
      uriTemplate(endpoints, "key", { key: "" }),
      null,
      { params: { label } }
    );
    if (response.status === 201) {
      keyList.push(response.data);
      dispatch({
        type: TYPES.SET_API_KEY_LIST,
        payload: keyList,
      });
      dispatch(showToast(SUCCESS, "API key created successfully"));

      dispatch(toggleNewAPIKeyModal(false));
      dispatch(setNewKeyLabel(""));
    } else {
      dispatch(showToast(DANGER, response.data.message));
    }
  } catch {
    dispatch(showToast(DANGER, ERROR_MSG));
  }
  dispatch({ type: TYPES.COMPLETED });
};

export const toggleNewAPIKeyModal = (isOpen) => ({
  type: TYPES.TOGGLE_NEW_KEY_MODAL,
  payload: isOpen,
});

export const setNewKeyLabel = (label) => ({
  type: TYPES.SET_NEW_KEY_LABEL,
  payload: label,
});
