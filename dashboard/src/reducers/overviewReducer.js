import * as TYPES from "../actions/types";
const initialState = {
  datasets: [],
  savedRuns: [],
  newRuns: [],
  defaultPerPage: 5,
  initNewRuns: [],
  selectedRuns: [],
  selectedSavedRuns: [],
  expiringRuns: [],
  isMetadataModalOpen: false,
  loadingDone: !!sessionStorage.getItem("loadingDone"),
  isRelayModalOpen: false,
  relayInput: "",
  treeData: [],
  checkedItems: ["dataset*access", "dataset*metalog*run"],
};

const OverviewReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.USER_RUNS:
      return {
        ...state,
        datasets: payload,
      };
    case TYPES.SAVED_RUNS:
      return {
        ...state,
        savedRuns: payload,
      };
    case TYPES.NEW_RUNS:
      return {
        ...state,
        newRuns: payload,
      };
    case TYPES.INIT_NEW_RUNS:
      return {
        ...state,
        initNewRuns: payload,
      };
    case TYPES.SELECTED_NEW_RUNS:
      return {
        ...state,
        selectedRuns: [...payload],
      };
    case TYPES.SELECTED_SAVED_RUNS:
      return {
        ...state,
        selectedSavedRuns: [...payload],
      };
    case TYPES.EXPIRING_RUNS:
      return {
        ...state,
        expiringRuns: payload,
      };
    case TYPES.SET_DASHBOARD_LOADING:
      return {
        ...state,
        isLoadingFirstTime: false,
      };
    case TYPES.SET_LOADING_FLAG:
      return {
        ...state,
        loadingDone: payload,
      };
    case TYPES.TOGGLE_RELAY_MODAL:
      return {
        ...state,
        isRelayModalOpen: payload,
      };
    case TYPES.SET_RELAY_DATA:
      return {
        ...state,
        relayInput: payload,
      };
    case TYPES.SET_METADATA_MODAL:
      return {
        ...state,
        isMetadataModalOpen: payload,
      };
    case TYPES.SET_METADATA_CHECKED_KEYS:
      return {
        ...state,
        checkedItems: payload,
      };
    case TYPES.SET_TREE_DATA:
      return {
        ...state,
        treeData: payload,
      };
    default:
      return state;
  }
};

export default OverviewReducer;
