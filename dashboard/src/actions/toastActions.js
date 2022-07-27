import * as TYPES from "./types";

export const showSessionExpired = () => async (dispatch) => {
  const toast = {
    variant: "danger",
    title: "Session Expired",
    message: "Please login to continue",
  };
  dispatch({
    type: TYPES.SHOW_TOAST,
    payload: toast,
  });
  dispatch(logout());
};

export const showFailureToast = () => async (dispatch) => {
  const toast = {
    variant: "danger",
    title: "Something went wrong",
    message: "Please try again later",
  };
  dispatch({
    type: TYPES.SHOW_TOAST,
    payload: toast,
  });
};

export const constructToast = (variant, title, message = "") => {
  return {
    type: TYPES.SHOW_TOAST,
    payload: { variant, title, message },
  };
};
