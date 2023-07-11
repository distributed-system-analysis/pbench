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
    if (error?.response && error.response?.data) {
      const errorMsg = error.response.data?.message;
      const isUnsupportedType = errorMsg
        ?.toLowerCase()
        .includes("unsupported benchmark");
      if (isUnsupportedType) {
        dispatch({
          type: TYPES.IS_UNSUPPORTED_TYPE,
          payload: errorMsg,
        });
      }
    } else {
      dispatch(showToast(DANGER, ERROR_MSG));
    }
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};

export const parseChartData = () => (dispatch, getState) => {
  const response = getState().comparison.data.data;
  const chartData = [];

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

    const datasets = [
      {
        label: run.instances[0].dataset_name,
        data: run.instances.map((i) => i.time_taken),
        backgroundColor: "#8BC1F7",
      },
    ];

    const data = {
      labels: run.instances.map((i) => i.name),
      id: `${run.test_name}_${run.metrics_unit}`,
      datasets,
    };

    const obj = { options, data };
    chartData.push(obj);
  }

  dispatch({
    type: TYPES.SET_PARSED_DATA,
    payload: chartData,
  });
};
