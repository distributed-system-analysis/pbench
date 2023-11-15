import * as TYPES from "../actions/types";

import { MY_DATASETS } from "assets/constants/compareConstants";
const initialState = {
  data: [],
  chartData: [],
  activeResourceId: "",
  unsupportedType: "",
  isCompareSwitchChecked: false,
  selectedResourceIds: [],
  unmatchedMessage: "",
  isChartModalOpen: false,
  activeChart: "",
  compareChartData: [],
  searchValue: "",
  datasetType: MY_DATASETS,
};

const ComparisonReducer = (state = initialState, action = {}) => {
  const { type, payload } = action;
  switch (type) {
    case TYPES.SET_QUISBY_DATA:
      return {
        ...state,
        data: payload,
      };
    case TYPES.SET_PARSED_DATA:
      return {
        ...state,
        chartData: payload,
      };
    case TYPES.SET_ACTIVE_RESOURCEID:
      return {
        ...state,
        activeResourceId: payload,
      };
    case TYPES.IS_UNSUPPORTED_TYPE:
      return {
        ...state,
        unsupportedType: payload,
      };
    case TYPES.TOGGLE_COMPARE_SWITCH:
      return {
        ...state,
        isCompareSwitchChecked: !state.isCompareSwitchChecked,
      };
    case TYPES.SET_SELECTED_RESOURCE_ID:
      return {
        ...state,
        selectedResourceIds: payload,
      };
    case TYPES.UNMATCHED_BENCHMARK_TYPES:
      return {
        ...state,
        unmatchedMessage: payload,
      };
    case TYPES.SET_CHART_MODAL:
      return {
        ...state,
        isChartModalOpen: payload,
      };
    case TYPES.SET_CURRENT_CHARTID:
      return {
        ...state,
        activeChart: payload,
      };
    case TYPES.SET_COMPARE_DATA:
      return {
        ...state,
        compareChartData: payload,
      };
    case TYPES.SET_SEARCH_VALUE:
      return {
        ...state,
        searchValue: payload,
      };
    case TYPES.SET_DATASET_TYPE:
      return {
        ...state,
        datasetType: payload,
      };
    default:
      return state;
  }
};

export default ComparisonReducer;
