import axios from "axios";
import { showSessionExpired } from "actions/toastActions";
import store from "store/store";

const { dispatch, getState } = store;

const axiosInstance = axios.create({ responseType: "json" });

axiosInstance.interceptors.request.use((req) => {
  const keycloak = getState().apiEndpoint.keycloak;
  if (keycloak?.authenticated) {
    req.headers.Authorization = `Bearer ${keycloak.token}`;
  }
  return req;
});
/** Intercept any unauthorized request.
 * dispatch logout action accordingly **/
const UNAUTHORIZED = 401;
axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response) {
      const { status } = error.response;
      const { responseURL } = error.request;
      if (status === UNAUTHORIZED && !responseURL.includes("login")) {
        dispatch(showSessionExpired());
      }
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;
