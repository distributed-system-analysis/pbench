import DatasetListReducer from "./datasetListReducer";
import EndpointReducer from "./endpointReducer";
import KeyManagementReducer from "./keyManagementReducer";
import LoadingReducer from "./loadingReducer";
import NavbarReducer from "./navbarReducer";
import OverviewReducer from "./overviewReducer";
import QuisbyChartReducer from "./quisbyChartReducer";
import SidebarReducer from "./sidebarReducer";
import TableOfContentReducer from "./tableOfContentReducer";
import ToastReducer from "./toastReducer";
import { combineReducers } from "redux";

export default combineReducers({
  toastReducer: ToastReducer,
  loading: LoadingReducer,
  navOpen: NavbarReducer,
  datasetlist: DatasetListReducer,
  apiEndpoint: EndpointReducer,
  overview: OverviewReducer,
  tableOfContent: TableOfContentReducer,
  sidebar: SidebarReducer,
  keyManagement: KeyManagementReducer,
  quisbyChart: QuisbyChartReducer,
});
