import * as TYPES from "./types";
import API from "../utils/axiosInstance";
import { showFailureToast, constructToast } from "./toastActions";

export const getProfileDetails = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });

    const username = getState().userAuth.loginDetails.username;
    const endpoints = getState().apiEndpoint.endpoints;

    const response = await API.get(`${endpoints?.api?.user}/${username}`);

    if (response.status === 200 && Object.keys(response.data).length > 0) {
      dispatch({
        type: TYPES.GET_USER_DETAILS,
        payload: response?.data,
      });
    } else {
      dispatch(showFailureToast());
    }
    dispatch({ type: TYPES.COMPLETED });
  } catch (error) {
    dispatch(constructToast("danger", error?.response?.data?.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
    dispatch({ type: TYPES.COMPLETED });
  }
};

export const updateUserDetails =
  (value, fieldName) => async (dispatch, getState) => {
    const userDetails = { ...getState().userProfile.userDetails };
    const updatedUserDetails = { ...getState().userProfile.updatedUserDetails };

    userDetails[fieldName] = value;
    updatedUserDetails[fieldName] = value;
    const payload = {
      userDetails,
      updatedUserDetails,
    };
    dispatch({
      type: TYPES.UPDATE_USER_DETAILS,
      payload,
    });
  };

export const sendForUpdate = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });

    const username = getState().userAuth.loginDetails.username;
    const endpoints = getState().apiEndpoint.endpoints;

    if (username) {
      const response = await API.put(`${endpoints?.api?.user}/${username}`, {
        ...getState().userProfile.updatedUserDetails,
      });
      if (response.status === 200) {
        dispatch(constructToast("success", "Updated!"));
        dispatch({
          type: TYPES.GET_USER_DETAILS,
          payload: response?.data,
        });
        dispatch({ type: TYPES.RESET_DATA });
        dispatch({ type: TYPES.COMPLETED });
        return false;
      } else {
        dispatch(showFailureToast());
        dispatch({ type: TYPES.COMPLETED });
        return false;
      }
    }
  } catch (error) {
    dispatch(constructToast("danger", error?.response?.data?.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
    dispatch({ type: TYPES.COMPLETED });
  }
};

export const resetUserDetails = () => async (dispatch, getState) => {
  dispatch({
    type: TYPES.SET_USER_DETAILS,
    payload: getState().userProfile.userDetails_copy,
  });
  dispatch({ type: TYPES.RESET_DATA });
};
