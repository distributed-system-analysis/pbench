import * as TYPES from "./types";

import API from "../utils/axiosInstance";
import { constructToast } from "./toastActions";

export const getDatasets = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });

    const username = await getState().userAuth.loginDetails.username;

    const params = new URLSearchParams();
    params.append("metadata", "dataset.created");
    params.append("metadata", "dataset.owner");
    params.append("metadata", "dataset.access");
    params.append("metadata", "server.deletion");
    params.append("metadata", "dashboard.saved");
    params.append("metadata", "dashboard.seen");
    params.append("metadata", "user.favorite");

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
          type: TYPES.GET_PRIVATE_DATASET,
          payload: data,
        });

        const savedRuns = data.filter(
          (item) => item.metadata["dashboard.saved"]
        );
        const newRuns = data.filter(
          (item) => !item.metadata["dashboard.saved"]
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
  save: "dashboard.saved",
  read: "dashboard.seen",
  favorite: "user.favorite",
};
/**
 * Filter the List of Datasets based on Date Range and Dataset Name
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
      // dispatch is awaited else toast message will appear before the UI updated
      await dispatch({
        type: TYPES.INIT_NEW_RUNS,
        payload: filteredInitRuns,
      });

      await dispatch({
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
  (method, value) => async (dispatch, getState) => {
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
