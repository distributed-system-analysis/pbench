import * as TYPES from "./types";
import API from "../utils/axiosInstance";
import * as API_ROUTES from "../utils/apiConstants";
import * as CONSTANTS from "../assets/constants/authConstants";
import Cookies from "js-cookie";
import { uid } from "../utils/helper";

export const makeLoginRequest =
  (details, navigate) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      // empty the alerts
      dispatch({
        type: TYPES.USER_NOTION_ALERTS,
        payload: [],
      });
      const response = await API.post(API_ROUTES.LOGIN, {
        ...details,
      });
      if (response.status === 200 && Object.keys(response.data).length > 0) {
        let keepUser = getState().userAuth.keepLoggedIn;
        let expiryTime = keepUser
          ? CONSTANTS.expiry_keepUser_days
          : CONSTANTS.expiry_default_days;
        Cookies.set("isLoggedIn", true, { expires: expiryTime, secure: true });
        Cookies.set("token", response.data?.auth_token, {
          expires: expiryTime,
          secure: true,
        });
        Cookies.set("username", response.data?.username, {
          expires: expiryTime,
          secure: true,
        });
        let loginDetails = {
          isLoggedIn: true,
          token: response.data?.auth_token,
          username: response.data?.username,
        };
        await dispatch({
          type: TYPES.SET_LOGIN_DETAILS,
          payload: loginDetails,
        });

        navigate("/");
        let toast = {
          variant: "success",
          title: "Logged in successfully",
        };
        dispatch({
          type: TYPES.SHOW_TOAST,
          payload: { ...toast },
        });
      }
      dispatch({ type: TYPES.COMPLETED });
    } catch (error) {
      let alerts = getState().userAuth.alerts;
      let alert = {};
      if (error?.response) {
        alert = {
          title: error?.response?.data?.message,
          key: uid(),
        };
        dispatch(toggleLoginBtn(true));
      } else {
        alert = {
          title: error?.message,
          key: uid(),
        };
        dispatch({ type: TYPES.NETWORK_ERROR });
      }
      alerts.push(alert);
      dispatch({
        type: TYPES.USER_NOTION_ALERTS,
        payload: alerts,
      });
      dispatch({ type: TYPES.COMPLETED });
    }
  };

export const movePage = (toPage, navigate) => async (dispatch) => {
  // empty the alerts
  dispatch({
    type: TYPES.USER_NOTION_ALERTS,
    payload: [],
  });
  navigate(toPage);
};

export const setUserLoggedInState = (value) => async (dispatch) => {
  dispatch({
    type: TYPES.KEEP_USER_LOGGED_IN,
    payload: value,
  });
};

export const registerUser =
  (details, navigate) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      // empty the alerts
      dispatch({
        type: TYPES.USER_NOTION_ALERTS,
        payload: [],
      });
      const endpoints = getState().apiEndpoint.endpoints;
      const response = await API.post(endpoints?.api?.register, {
        ...details,
      });
      if (response.status === 200) {
        navigate("/login");
      }
      dispatch({ type: TYPES.COMPLETED });
    } catch (error) {
      let alerts = getState().userAuth.alerts;
      let amsg = {};
      document.querySelector(".signup-card").scrollTo(0, 0);
      if (error?.response) {
        amsg = error?.response?.data?.message;
        dispatch(toggleSignupBtn(true));
      } else {
        amsg = error?.message;
        dispatch({ type: TYPES.NETWORK_ERROR });
      }
      let alert = { title: amsg, key: uid() };
      alerts.push(alert);
      dispatch({
        type: TYPES.USER_NOTION_ALERTS,
        payload: alerts,
      });
      dispatch({ type: TYPES.COMPLETED });
    }
  };

export const toggleSignupBtn = (isDisabled) => async (dispatch) => {
  dispatch({
    type: TYPES.SET_SIGNUP_BUTTON,
    payload: isDisabled,
  });
};

export const toggleLoginBtn = (isDisabled) => async (dispatch) => {
  dispatch({
    type: TYPES.SET_LOGIN_BUTTON,
    payload: isDisabled,
  });
};

export const getUserDetails = () => async (dispatch) => {
  let loginDetails = {
    isLoggedIn: Cookies.get("isLoggedIn"),
    token: Cookies.get("token"),
    username: Cookies.get("username"),
  };
  dispatch({
    type: TYPES.SET_LOGIN_DETAILS,
    payload: loginDetails,
  });
};
export const logout = () => async (dispatch) => {
  dispatch({ type: TYPES.LOADING });
  let keys = ["username", "token", "isLoggedIn"];
  for (let key of keys) {
    Cookies.remove(key);
  }
  dispatch({ type: TYPES.COMPLETED });
  setTimeout(() => {
    window.location.href = "login";
  }, CONSTANTS.logout_delay_ms);
};
