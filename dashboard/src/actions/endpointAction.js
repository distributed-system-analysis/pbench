import * as TYPES from "./types";
import Keycloak from "keycloak-js";

export const fetchEndpoints = async (dispatch) => {
  try {
    const response = await fetch("/api/v1/endpoints");

    if (!response.ok) {
      throw new Error(`Network error! status: ${response.status}`);
    }
    const data = await response.json();
    dispatch({
      type: TYPES.SET_ENDPOINTS,
      payload: data,
    });
    const keycloak = new Keycloak({
      url: data?.openid?.server,
      realm: data?.openid?.realm,
      clientId: data?.openid?.client,
    });
    dispatch({
      type: TYPES.SET_KEYCLOAK,
      payload: keycloak,
    });
  } catch (error) {
    dispatch({
      type: TYPES.SHOW_TOAST,
      payload: {
        variant: "danger",
        title: `Something went wrong, ${error}`,
      },
    });
  }
};
