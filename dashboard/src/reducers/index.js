import { combineReducers } from 'redux';
import ToastReducer from "./toastReducer";
import LoadingReducer from "./loadingReducer";
import AuthReducer from "./authReducer";

export default combineReducers({
    toastReducer: ToastReducer,
    loading: LoadingReducer,
    userAuth: AuthReducer
})