import * as TYPES from "./types.js";

import API from "../utils/axiosInstance";
import { DANGER } from "assets/constants/toastConstants";
import { showToast } from "./toastActions";

const chartTitleMap = {
  gb_sec: "Bandwidth",
  trans_sec: "Transactions/second",
  usec: "Latency",
};

export const getQuisbyData =
  (params, navigate, isMultiple) => async (dispatch) => {
    try {
      dispatch({ type: TYPES.LOADING });
      let newPageURL = "";
      if (!isMultiple) {
        newPageURL = `/dashboard/quisby-results/${params[0].name}/${params[0].rid}`;
      } else {
        newPageURL = `/dashboard/quisby-compare`;
      }

      const response = await API.post(
        "http://10.1.170.224:4000/quisby/get_metrics_data/",
        {
          resource_id: params,
        }
      );
      if (response.status === 200 && response.data?.jsonData) {
        dispatch({
          type: TYPES.SET_QUISBY_DOC_LINK,
          payload: response.data.sheet_url,
        });

        dispatch({
          type: TYPES.GET_QUISBY_DATA,
          payload: response.data.jsonData.data,
        });

        dispatch(parseChartData());
        if (navigate) {
          navigate(newPageURL);
        }
      }
      dispatch({ type: TYPES.COMPLETED });
    } catch (error) {
      dispatch(showToast(DANGER, error?.response?.data?.status));
      dispatch({ type: TYPES.COMPLETED });
      dispatch({ type: TYPES.NETWORK_ERROR });
    }
  };

export const parseChartData = () => (dispatch, getState) => {
  const response = getState().quisbyChart.data;
  const COLORS = ["#8BC1F7", "#0066CC", "#519DE9", "#004B95", "#002F5D"];

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
          text: "",
        },
      },
      scales: {
        x: {
          title: {
            display: true,
            text: "",
          },
        },
        y: {
          title: {
            display: true,
            text: "",
          },
        },
      },
    };
    options.scales.x.title["text"] = "Instance Count";
    options.scales.y.title["text"] = run.metrics_unit;
    options.plugins.title["text"] = `Uperf: ${
      chartTitleMap[run.metrics_unit?.toLowerCase()]
    } | ${run.test_name}`;

    const datasets = [];
    for (const item of run.result) {
      const obj = {
        label: item.run_name,
        data: item.instances.map((i) => i.time_taken),
        backgroundColor: COLORS[i],
      };
      i++;
      datasets.push(obj);
    }
    const data = {
      labels: run?.result[0]?.instances.map((i) => i.name),
      id: `${run.test_name}_${run.metrics_unit}`,
      datasets,
    };
    const id = `${run.test_name}_${run.metrics_unit}`;
    const obj = { options, data, id };
    chartData.push(obj);
    i = 0;
  }

  dispatch({
    type: TYPES.SET_PARSED_DATA,
    payload: chartData,
  });
};

export const constructQuisbyRequest = (navigate) => (dispatch, getState) => {
  const selectedRuns = getState().overview.selectedRuns;

  const params = [];

  for (const element of selectedRuns) {
    let obj = {};
    // eslint-disable-next-line camelcase
    const { name, resource_id } = element;
    // eslint-disable-next-line camelcase
    obj = { name, rid: resource_id };
    params.push(obj);
  }
  const isMultiple = selectedRuns.length > 1 ? true : false;
  dispatch(getQuisbyData(params, navigate, isMultiple)); // 3rd param to indicate comparison
};
