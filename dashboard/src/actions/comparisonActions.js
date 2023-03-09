import * as TYPES from "./types.js";

import { DANGER, ERROR_MSG } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import { showToast } from "./toastActions";
import { uriTemplate } from "../utils/helper";

const chartTitleMap = {
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
      dispatch(parseChartData());
    }
  } catch (error) {
    if (
      error?.response?.data &&
      error.response.data?.message
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
const COLORS = ["#8BC1F7", "#0066CC", "#519DE9", "#004B95", "#002F5D"];
export const parseChartData = () => (dispatch, getState) => {
  const response = getState().comparison.data.data;
  const isCompareSwitchChecked = getState().comparison.isCompareSwitchChecked;
  const chartData = [];
  let i = 0;

  for (const run of response) {
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
          text: `Uperf: ${chartTitleMap[run.metrics_unit.toLowerCase()]} | ${
            run.test_name
          }`,
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
            text: run.metrics_unit,
          },
        },
      },
    };
    /* for single */
    // const datasets = [
    //   {
    //     label: run.instances[0].dataset_name,
    //     data: run.instances.map((i) => i.time_taken),
    //     backgroundColor: "#8BC1F7",
    //   },
    // ];
    /* for single */
    const datasets = [];
    /* mutilple happy path*/
    // for (const item of run.instances) {
    //   const obj = {
    //     label: item.dataset_name,
    //     data: item.time_taken.trim(),
    //     backgroundColor: COLORS[i],
    //   };
    //   i++;
    //   datasets.push(obj);
    // }
    /* mutilple happy path*/

    const data = {
      labels: [...new Set(run.instances.map((i) => i.name))],
      id: `${run.test_name}_${run.metrics_unit}`,
      datasets,
    };
    const result = run.instances.reduce(function (r, a) {
      r[a.dataset_name] = r[a.dataset_name] || [];
      r[a.dataset_name].push(a);
      return r;
    }, Object.create(null));

    for (const [key, value] of Object.entries(result)) {
      console.log(key);

      const map = {};
      for (const element of value) {
        map[element.name] = element.time_taken.trim();
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

export const toggleCompareSwitch = () => (dispatch, getState) => {
  dispatch({
    type: TYPES.TOGGLE_COMPARE_SWITCH,
    payload: !getState().comparison.isCompareSwitchChecked,
  });
};

export const setSelectedId = (isChecked, rId) => (dispatch, getState) => {
  let selectedIds = [...getState().comparison.selectedResourceIds];
  if (isChecked) {
    selectedIds = [...selectedIds, rId];
  } else {
    selectedIds = selectedIds.filter((item) => item !== rId);
  }
  dispatch({
    type: TYPES.SET_SELECTED_RESOURCE_ID,
    payload: selectedIds,
  });
};

export const compareMultipleDatasets = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });

    const endpoints = getState().apiEndpoint.endpoints;
    const selectedIds = [...getState().comparison.selectedResourceIds];

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
      dispatch(parseChartData());
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
