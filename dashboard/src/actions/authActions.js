import * as APP_ROUTES from "utils/routeConstants";
import * as CONSTANTS from "../assets/constants/authConstants";
import * as TYPES from "./types";

import API from "../utils/axiosInstance";
import Cookies from "js-cookie";
import { SUCCESS } from "assets/constants/overviewConstants";
import { showToast } from "actions/toastActions";
import { uid } from "../utils/helper";


// Create an Authentication Request
export const authenticationRequest = () => async (dispatch, getState) => {
    try {
      const endpoints = getState().apiEndpoint.endpoints;
      const oidcServer = endpoints.openid.server;
      const oidcRealm = endpoints.openid.realm;
      const oidcClient = endpoints.openid.client;
      // URI parameters ref: https://openid.net/specs/openid-connect-core-1_0.html#AuthorizationEndpoint
      // Refer Step 3 of pbench/docs/user_authentication/third_party_token_management.md
      const uri = `${oidcServer}/realms/${oidcRealm}/protocol/openid-connect/auth`;
      const queryParams = [
        'client_id=' + oidcClient,
        'response_type=code',
        'redirect_uri=' + window.location.href.split('?')[0],
        'scope=profile',
        'prompt=login',
        'max_age=120'
      ];
      window.location.href = uri + '?' + queryParams.join('&');
    } catch (error) {
      const alerts = getState().userAuth.alerts;
      dispatch(error?.response
        ? toggleLoginBtn(true)
        : { type: TYPES.OPENID_ERROR }
      );
      const alert = {
          title: error?.response ? error.response.data?.message : error?.message,
          key: uid(),
      };
      dispatch({
        type: TYPES.USER_NOTION_ALERTS,
        payload: [...alerts, alert],
      });
      dispatch({ type: TYPES.COMPLETED });
    }
};

export const makeLoginRequest =
  (details, navigate) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      // empty the alerts
      dispatch({
        type: TYPES.USER_NOTION_ALERTS,
        payload: [],
      });
      const endpoints = getState().apiEndpoint.endpoints;
      const response = await API.post(endpoints?.api?.login, {
        ...details,
      });
      if (response.status === 200 && Object.keys(response.data).length > 0) {
        const keepUser = getState().userAuth.keepLoggedIn;
        const expiryTime = keepUser
          ? CONSTANTS.EXPIRY_KEEPUSER_DAYS
          : CONSTANTS.EXPIRY_DEFAULT_DAYS;
        Cookies.set("isLoggedIn", true, { expires: expiryTime });
        Cookies.set("token", response.data?.auth_token, {
          expires: expiryTime,
        });
        Cookies.set("username", response.data?.username, {
          expires: expiryTime,
        });
        const loginDetails = {
          isLoggedIn: true,
          token: response.data?.auth_token,
          username: response.data?.username,
        };
        await dispatch({
          type: TYPES.SET_LOGIN_DETAILS,
          payload: loginDetails,
        });

        navigate(APP_ROUTES.OVERVIEW);

        dispatch(showToast(SUCCESS, "Logged in successfully!"));
      }
      dispatch({ type: TYPES.COMPLETED });
    } catch (error) {
      const alerts = getState().userAuth.alerts;
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
      if (response.status === 201) {
        dispatch(showToast(SUCCESS, "Account created!", "Login to continue"));
        navigate(APP_ROUTES.AUTH_LOGIN);
      }
      dispatch({ type: TYPES.COMPLETED });
    } catch (error) {
      const alerts = getState().userAuth.alerts;
      let amsg = {};
      document.querySelector(".signup-card").scrollTo(0, 0);
      if (error?.response) {
        amsg = error?.response?.data?.message;
        dispatch(toggleSignupBtn(true));
      } else {
        amsg = error?.message;
        dispatch({ type: TYPES.NETWORK_ERROR });
      }
      const alert = { title: amsg, key: uid() };
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
  const loginDetails = {
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
  const keys = ["username", "token", "isLoggedIn"];
  for (const key of keys) {
    Cookies.remove(key);
  }
  dispatch({ type: TYPES.COMPLETED });
  setTimeout(() => {
    window.location.href = APP_ROUTES.AUTH;
  }, CONSTANTS.LOGOUT_DELAY_MS);
};
