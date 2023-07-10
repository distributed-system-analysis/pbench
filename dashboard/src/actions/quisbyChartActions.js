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
        type: TYPES.GET_QUISBY_DATA,
        payload: response.data.json_data,
      });
      dispatch({
        type: TYPES.IS_UNSUPPORTED_TYPE,
        payload: "",
      });
      dispatch(parseChartData());
    }
    dispatch({ type: TYPES.COMPLETED });
  } catch (error) {
    if (error?.response) {
      const errorMsg = error.response.data.message;
      const isUnsupportedType = errorMsg?.toLowerCase().includes("unsupported");
      if (isUnsupportedType) {
        dispatch({
          type: TYPES.IS_UNSUPPORTED_TYPE,
          payload: errorMsg,
        });
      }
    } else {
      dispatch(showToast(DANGER, ERROR_MSG));
    }

    dispatch({ type: TYPES.COMPLETED });
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
};

export const parseChartData = () => (dispatch, getState) => {
  const response = getState().quisbyChart.data.data;
  const COLORS = ["#8BC1F7", "#0066CC", "#519DE9", "#004B95", "#002F5D"];

  const chartData = [];
  const i = 0; // used to iterate over the colors, will be used for comparsion
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
          text: `Uperf: ${chartTitleMap[run.metrics_unit?.toLowerCase()]} | ${
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

    const datasets = [
      {
        label: run.instances[0].dataset_name,
        data: run?.instances.map((i) => i.time_taken),
        backgroundColor: COLORS[i],
      },
    ];

    const data = {
      labels: run?.instances.map((i) => i.name),
      id: `${run.test_name}_${run.metrics_unit}`,
      datasets,
    };
    const id = `${run.test_name}_${run.metrics_unit}`;
    const obj = { options, data, id };
    chartData.push(obj);
  }

  dispatch({
    type: TYPES.SET_PARSED_DATA,
    payload: chartData,
  });
};
