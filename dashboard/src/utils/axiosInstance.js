import axios from "axios";
import Cookies from "js-cookie";
import { showSessionExpired } from "actions/toastActions";
import store from "store/store";

const { dispatch } = store;

const axiosInstance = axios.create({ responseType: "json" });

axiosInstance.interceptors.request.use(async (req) => {
  const token = Cookies.get("token");
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
