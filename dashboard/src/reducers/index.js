import { combineReducers } from "redux";
import ToastReducer from "./toastReducer";
import LoadingReducer from "./loadingReducer";
import AuthReducer from "./authReducer";
import NavbarReducer from "./navbarReducer";

export default combineReducers({
    toastReducer: ToastReducer,
    loading: LoadingReducer,
    userAuth: AuthReducer,
    navOpen:NavbarReducer
})
