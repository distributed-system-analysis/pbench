import axios from "axios";
import { LOCAL_BASE_URL } from "./apiConstants";
import Cookies from "js-cookie";
import { showSessionExpired } from "actions/toastActions";
import store from "store/store";

const { dispatch } = store;

let token = Cookies.get("token");

const axiosInstance = axios.create({
  baseURL: LOCAL_BASE_URL,
  responseType: "json",
});

axiosInstance.interceptors.request.use(async (req) => {
  token = Cookies.get("token");
  if (token) {
    req.headers.Authorization = `Bearer ${token}`;
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
