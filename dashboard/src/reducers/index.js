import { combineReducers } from 'redux';
import ToastReducer from "./toastReducer";
import LoadingReducer from "./loadingReducer";

export default combineReducers({
    toastReducer: ToastReducer,
    loading: LoadingReducer
})