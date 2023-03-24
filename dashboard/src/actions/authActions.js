import * as APP_ROUTES from "utils/routeConstants";
import * as CONSTANTS from "../assets/constants/authConstants";
import * as TYPES from "./types";

import Cookies from "js-cookie";
import { SUCCESS } from "assets/constants/overviewConstants";
import { showToast, clearToast } from "actions/toastActions";

/**
 * Wait for the Pbench Server endpoints to be loaded.
 * @param {getState} getState object.
 * @return {promise} promise object
 */
export async function waitForEndpoints(getState) {
  const waitStart = Date.now();
  /**
   * Settle the wait-for-endpoints promise.
   * @param {resolve} resolve object.
   * @param {reject} reject object
   */
  function check(resolve, reject) {
    if (Object.keys(getState().apiEndpoint.endpoints).length !== 0) {
      resolve("Endpoints loaded");
    } else if (Date.now() - waitStart > CONSTANTS.MAX_WAIT_MS) {
      reject(new Error("Timed out waiting for endpoints request"));
    } else {
      setTimeout(check, 250, resolve, reject);
    }
  }
  return new Promise((resolve, reject) => check(resolve, reject));
}

// Perform some house keeping when the user logs in
export const authCookies = () => async (dispatch, getState) => {
  await waitForEndpoints(getState);
  const keycloak = getState().apiEndpoint.keycloak;
  if (keycloak.authenticated) {
    // Set the isLoggedIn cookie with an expiry of OIDC refresh token.
    // We have to convert the UNIX epoch seconds returned by the refresh token
    // expiry to milliseconds before we can use it for creating a Date object.
    Cookies.set("isLoggedIn", true, {
      expires: new Date(keycloak.refreshTokenParsed.exp * 1000),
    });
    dispatch(showToast(SUCCESS, "Logged in successfully!"));
  }
};

export const movePage = (toPage, navigate) => async (dispatch) => {
  // clear all the toasts before navigating to another page
  dispatch(clearToast());
  navigate(toPage);
};

/**
 * Clear the local cookies and re-direct to the auth page.
 * @param {dispatch} dispatch object.
 */
export async function clearCachedSession(dispatch) {
  dispatch({ type: TYPES.LOADING });
  Cookies.remove("isLoggedIn");
  dispatch({ type: TYPES.COMPLETED });
  setTimeout(() => {
    window.location.href = APP_ROUTES.AUTH;
  }, CONSTANTS.LOGOUT_DELAY_MS);
}

export const sessionLogout = () => async (dispatch, getState) => {
  const keycloak = getState().apiEndpoint.keycloak;
  keycloak.logout();
  clearCachedSession(dispatch);
};
