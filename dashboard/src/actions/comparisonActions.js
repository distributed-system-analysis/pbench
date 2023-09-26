import * as CONSTANTS from "assets/constants/compareConstants";
import * as TYPES from "./types.js";

import { DANGER, ERROR_MSG, WARNING } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import { showToast } from "./toastActions";
import { uriTemplate } from "../utils/helper";

const uperfChartTitleMap = {
  gb_sec: "Bandwidth",
  trans_sec: "Transactions/second",
  usec: "Latency",
};

export const getQuisbyData = (dataset) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    dispatch({
      type: TYPES.SET_ACTIVE_RESOURCEID,
      payload: dataset.resource_id,
    });
    const response = await API.get(
      uriTemplate(endpoints, "datasets_visualize", {
        dataset: dataset.resource_id,
      })
    );
    if (response.status === 200 && response.data.json_data) {
      dispatch({
        type: TYPES.SET_QUISBY_DATA,
        payload: response.data.json_data,
      });
      dispatch({
        type: TYPES.IS_UNSUPPORTED_TYPE,
        payload: "",
      });
      dispatch(parseChartData(response.data.benchmark));
    }
  } catch (error) {
    if (
      error?.response?.data?.message
        ?.toLowerCase()
        .includes("unsupported benchmark")
    ) {
      dispatch({
        type: TYPES.IS_UNSUPPORTED_TYPE,
        payload: error.response.data.message,
      });
    } else {
      dispatch(showToast(DANGER, ERROR_MSG));
    }
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};
const COLORS = [
  CONSTANTS.COLOR1,
  CONSTANTS.COLOR2,
  CONSTANTS.COLOR3,
  CONSTANTS.COLOR4,
  CONSTANTS.COLOR5,
];

const getChartValues = (run, benchmarkType) => {
  const benchmark = benchmarkType.toLowerCase();
  const chartTitle = {
    uperf: `Uperf: ${uperfChartTitleMap[run.metrics_unit.toLowerCase()]} | ${
      run.test_name
    }`,
    fio: `Fio: ${run.test_name} | ${run.metrics_unit.toLowerCase()}`,
  };
  const yaxisTitle = {
    uperf: run.metrics_unit,
    fio: "Mb/sec",
  };
  const keys = {
    uperf: "name",
    fio: "iteration_name",
  };
  const values = {
    uperf: "time_taken",
    fio: "value",
  };
  const obj = {
    chartTitle: chartTitle[benchmark],
    yAxis: yaxisTitle[benchmark],
    keyToParse: keys[benchmark],
    valueToGet: values[benchmark],
  };

  return obj;
};
export const parseChartData = (benchmark) => (dispatch, getState) => {
  const response = getState().comparison.data.data;
  const isCompareSwitchChecked = getState().comparison.isCompareSwitchChecked;
  const chartData = [];
  let i = 0;

  for (const run of response) {
    const chartObj = getChartValues(run, benchmark);
    const options = {
      responsive: true,
      maintainAspectRatio: false,

      plugins: {
        colors: {
          forceOverride: true,
        },
        legend: {
          display: true,
          position: "bottom",
        },
        title: {
          display: true,
          text: chartObj.chartTitle,
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "Instance Count",
          },
        },
        y: {
          title: {
            display: true,
            text: chartObj.yAxis,
          },
        },
      },
    };

    const datasets = [];
    const data = {
      labels: [...new Set(run.instances.map((i) => i[chartObj.keyToParse]))],
      id: `${run.test_name}_${run.metrics_unit}`,
      datasets,
    };
    const result = run.instances.reduce(function (r, a) {
      r[a.dataset_name] = r[a.dataset_name] || [];
      r[a.dataset_name].push(a);
      return r;
    }, Object.create(null));

    for (const [key, value] of Object.entries(result)) {
      const map = {};
      for (const element of value) {
        map[element[chartObj.keyToParse]] = element[chartObj.valueToGet].trim();
      }
      const mappedData = data.labels.map((label) => {
        return map[label];
      });
      const obj = { label: key, backgroundColor: COLORS[i], data: mappedData };
      i++;
      datasets.push(obj);
    }

    const obj = { options, data };
    chartData.push(obj);
    i = 0;
  }
  const type = isCompareSwitchChecked
    ? TYPES.SET_COMPARE_DATA
    : TYPES.SET_PARSED_DATA;

  dispatch({
    type,
    payload: chartData,
  });
};

export const toggleCompareSwitch = () => ({
  type: TYPES.TOGGLE_COMPARE_SWITCH,
});

export const setSelectedId = (isChecked, rId) => (dispatch, getState) => {
  const prev = getState().comparison.selectedResourceIds;
  const selectedIds = isChecked
    ? [...prev, rId]
    : prev.filter((id) => id !== rId);

  if (selectedIds.length > CONSTANTS.MAX_DATASETS_COMPARE) {
    dispatch(
      showToast(
        WARNING,
        `Not more than ${CONSTANTS.MAX_DATASETS_COMPARE} datasets can be compared`
      )
    );
  } else {
    dispatch({
      type: TYPES.SET_SELECTED_RESOURCE_ID,
      payload: selectedIds,
    });
  }
};

export const compareMultipleDatasets = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });

    const endpoints = getState().apiEndpoint.endpoints;
    const selectedIds = getState().comparison.selectedResourceIds;

    const params = new URLSearchParams();
    params.append("datasets", selectedIds.toString());
    const response = await API.get(
      uriTemplate(endpoints, "datasets_compare", {}),
      { params }
    );
    if (response.status === 200 && response.data.json_data) {
      dispatch({
        type: TYPES.SET_QUISBY_DATA,
        payload: response.data.json_data,
      });
      dispatch({
        type: TYPES.UNMATCHED_BENCHMARK_TYPES,
        payload: "",
      });
      dispatch(parseChartData(response.data.benchmark));
    }
  } catch (error) {
    if (
      error?.response?.data &&
      error.response.data?.message
        ?.toLowerCase()
        .includes("benchmarks must match")
    ) {
      dispatch({
        type: TYPES.UNMATCHED_BENCHMARK_TYPES,
        payload: error.response.data.message,
      });
    } else {
      dispatch(showToast(DANGER, ERROR_MSG));
    }
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};

export const setChartModalContent = (chartId) => (dispatch, getState) => {
  const isCompareSwitchChecked = getState().comparison.isCompareSwitchChecked;
  const data = isCompareSwitchChecked
    ? getState().comparison.compareChartData
    : getState().comparison.chartData;

  const activeChart = data.filter((item) => item.data.id === chartId)[0];

  dispatch({
    type: TYPES.SET_CURRENT_CHARTID,
    payload: activeChart,
  });
};

export const setChartModal = (isOpen) => ({
  type: TYPES.SET_CHART_MODAL,
  payload: isOpen,
});

export const setSearchValue = (value) => ({
  type: TYPES.SET_SEARCH_VALUE,
  payload: value,
});
