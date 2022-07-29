import * as TYPES from "./types";

import API from "../utils/axiosInstance";
import { constructToast } from "./toastActions";

const DATASET_ACCESS = "dataset.access"
const DATASET_CREATED = "dataset.created"
const DATASET_OWNER = "dataset.owner"
const DASHBOARD_SAVED = "global.dashboard.saved"
const DASHBOARD_SEEN = "global.dashboard.seen"
const SERVER_DELETION = "server.deletion"
const USER_FAVORITE = "user.dashboard.favorite"

export const getDatasets = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });

    const username = getState().userAuth.loginDetails.username;

    const params = new URLSearchParams();
    params.append("metadata", DATASET_CREATED);
    params.append("metadata", DATASET_OWNER);
    params.append("metadata", DATASET_ACCESS);
    params.append("metadata", SERVER_DELETION);
    params.append("metadata", DASHBOARD_SAVED);
    params.append("metadata", DASHBOARD_SEEN);
    params.append("metadata", USER_FAVORITE);

    params.append("owner", username);

    const endpoints = getState().apiEndpoint.endpoints;
    const defaultPerPage = getState().overview.defaultPerPage;

    const response = await API.get(endpoints?.api?.datasets_list, {
      params: params,
    });

    if (response.status === 200) {
      if (response?.data?.results?.length > 0) {
        const data = response.data.results;
        dispatch({
          type: TYPES.USER_RUNS,
          payload: data,
        });

        const savedRuns = data.filter(
          (item) => item.metadata[DASHBOARD_SAVED]
        );
        const newRuns = data.filter(
          (item) => !item.metadata[DASHBOARD_SAVED]
        );

        dispatch({
          type: TYPES.SAVED_RUNS,
          payload: savedRuns,
        });
        dispatch({
          type: TYPES.NEW_RUNS,
          payload: newRuns,
        });
        dispatch({
          type: TYPES.INIT_NEW_RUNS,
          payload: newRuns?.slice(0, defaultPerPage),
        });
      }
    }
  } catch (error) {
    dispatch(constructToast("danger", error?.response?.data?.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};

const metaDataActions = {
  save: DASHBOARD_SAVED,
  read: DASHBOARD_SEEN,
  favorite: USER_FAVORITE,
};
/**
 * Function which return a thunk to be passed to a Redux dispatch() call
 * @function
 * @param {Object} dataset - Dataset which is being updated
 * @param {string} actionType - Action (save, read, favorite) being performed
 * @param {string} actionValue - Value to be updated (true/ false)
 * @return {Object} - dispatch the action and update the state
 */

export const updateDataset =
  (dataset, actionType, actionValue) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      const savedRuns = getState().overview.savedRuns;
      const newRuns = getState().overview.newRuns;
      const initNewRuns = getState().overview.initNewRuns;

      const method = metaDataActions[actionType];

      const endpoints = getState().apiEndpoint.endpoints;
      const response = await API.put(
        `${endpoints?.api?.datasets_metadata}/${dataset.resource_id}`,
        {
          metadata: { [method]: actionValue },
        }
      );
      if (response.status === 200) {
        if (actionType === "save") {
          savedRuns.push(dataset);
          const filteredNewRuns = newRuns.filter(
            (item) => item.resource_id !== dataset.resource_id
          );
          const filteredInitRuns = initNewRuns.filter(
            (item) => item.resource_id !== dataset.resource_id
          );
          dispatch({
            type: TYPES.SAVED_RUNS,
            payload: savedRuns,
          });
          dispatch({
            type: TYPES.INIT_NEW_RUNS,
            payload: filteredInitRuns,
          });
          dispatch({
            type: TYPES.NEW_RUNS,
            payload: filteredNewRuns,
          });
        } else {
          const dataIndex = newRuns.findIndex(
            (item) => item.resource_id === dataset.resource_id
          );
          newRuns[dataIndex].metadata[metaDataActions[actionType]] =
            response.data[metaDataActions[actionType]];
          dispatch({
            type: TYPES.NEW_RUNS,
            payload: newRuns,
          });
        }
      } else {
        dispatch(constructToast("danger", response?.data?.message));
      }
    } catch (error) {
      dispatch(constructToast("danger", error?.response?.data?.message));
      dispatch({ type: TYPES.NETWORK_ERROR });
    }
    dispatch({ type: TYPES.COMPLETED });
  };

export const deleteDataset = (dataset) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.post(
      `${endpoints?.api?.datasets_delete}/${dataset.resource_id}`
    );
    if (response.status === 200) {
      const datasets = getState().overview.newRuns;
      const initNewRuns = getState().overview.initNewRuns;
      const result = datasets.filter(
        (item) => item.resource_id !== dataset.resource_id
      );
      const filteredInitRuns = initNewRuns.filter(
        (item) => item.resource_id !== dataset.resource_id
      );

      dispatch({
        type: TYPES.INIT_NEW_RUNS,
        payload: filteredInitRuns,
      });

      dispatch({
        type: TYPES.NEW_RUNS,
        payload: result,
      });
      dispatch(constructToast("success", "Deleted!"));
    }
  } catch (error) {
    dispatch(constructToast("danger", error?.response?.data?.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
};

export const setRows = (rows) => {
  return {
    type: TYPES.INIT_NEW_RUNS,
    payload: rows,
  };
};

export const setSelectedRuns = (rows) => {
  return {
    type: TYPES.SELECTED_NEW_RUNS,
    payload: rows,
  };
};

export const updateMultipleDataset =
  (method, value) => (dispatch, getState) => {
    const selectedRuns = getState().overview.selectedRuns;

    if (selectedRuns.length > 0) {
      selectedRuns.forEach((item) =>
        method === "delete"
          ? dispatch(deleteDataset(item))
          : dispatch(updateDataset(item, method, value))
      );
      const toastMsg =
        method === "delete"
          ? "Deleted!"
          : method === "save"
          ? "Saved!"
          : "Updated!";
      dispatch(constructToast("success", toastMsg));
      dispatch(setSelectedRuns([]));
    } else {
      dispatch(constructToast("warning", "Select dataset(s) for update"));
    }
  };
