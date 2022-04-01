import { combineReducers } from "redux";
import ToastReducer from "./toastReducer";
import LoadingReducer from "./loadingReducer";
import AuthReducer from "./authReducer";
import NavbarReducer from "./navbarReducer";
import DatasetListReducer from "./datasetListReducer";
import EndpointReducer from "./endpointReducer";
import UserProfileReducer from "./userProfileReducer";
import OverviewReducer from "./overviewReducer";

export default combineReducers({
  toastReducer: ToastReducer,
  loading: LoadingReducer,
  userAuth: AuthReducer,
  userProfile: UserProfileReducer,
  navOpen: NavbarReducer,
  datasetlist: DatasetListReducer,
  apiEndpoint: EndpointReducer,
  overview: OverviewReducer,
});
