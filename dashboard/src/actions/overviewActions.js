import * as TYPES from "./types";

import {
  DASHBOARD_LOAD_DELAY_MS,
  DASHBOARD_SAVED,
  DASHBOARD_SEEN,
  DATASET_ACCESS,
  DATASET_CREATED,
  DATASET_NAME,
  DATASET_NAME_LENGTH,
  DATASET_OWNER,
  EXPIRATION_DAYS_LIMIT,
  SERVER_DELETION,
  USER_FAVORITE,
} from "assets/constants/overviewConstants";

import API from "../utils/axiosInstance";
import { findNoOfDays } from "utils/dateFunctions";
import { showToast } from "./toastActions";

export const getDatasets = () => async (dispatch, getState) => {
  const alreadyRendered = getState().overview.loadingDone;
  try {
    const username = getState().userAuth.loginDetails.username;

    if (alreadyRendered) {
      dispatch({ type: TYPES.LOADING });
    }
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

        dispatch(initializeRuns());
      }
    }
  } catch (error) {
    dispatch(showToast("danger", error?.response?.data?.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  if (alreadyRendered) {
    dispatch({ type: TYPES.COMPLETED });
  } else {
    dispatch(setLoadingDoneFlag());
  }
};

const initializeRuns = () => (dispatch, getState) => {
  const data = getState().overview.datasets;
  data.forEach((item) => {
    item["isEdit"] = false;
    item["name_copy"] = item.name;
    item["isDirty"] = false;
    item["name_validated"] = "default";
    item["isItemSeen"] = !!item?.metadata?.[DASHBOARD_SEEN];
    item["isItemFavorited"] = !!item?.metadata?.[USER_FAVORITE];
  });
  const defaultPerPage = getState().overview.defaultPerPage;

  const savedRuns = data.filter((item) => item.metadata[DASHBOARD_SAVED]);
  const newRuns = data.filter((item) => !item.metadata[DASHBOARD_SAVED]);

  const expiringRuns = data.filter(
    (item) =>
      findNoOfDays(item.metadata["server.deletion"]) < EXPIRATION_DAYS_LIMIT
  );
  dispatch({
    type: TYPES.EXPIRING_RUNS,
    payload: expiringRuns,
  });
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
};
const metaDataActions = {
  save: DASHBOARD_SAVED,
  read: DASHBOARD_SEEN,
  favorite: USER_FAVORITE,
  datasetName: DATASET_NAME,
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

      const runs = getState().overview.datasets;

      const method = metaDataActions[actionType];

      const endpoints = getState().apiEndpoint.endpoints;
      const response = await API.put(
        `${endpoints?.api?.datasets_metadata}/${dataset.resource_id}`,
        {
          metadata: { [method]: actionValue },
        }
      );
      if (response.status === 200) {
        const dataIndex = runs.findIndex(
          (item) => item.resource_id === dataset.resource_id
        );
        runs[dataIndex].metadata[metaDataActions[actionType]] =
          response.data[metaDataActions[actionType]];
        dispatch({
          type: TYPES.USER_RUNS,
          payload: runs,
        });
        dispatch(initializeRuns());
      } else {
        dispatch(showToast("danger", response?.data?.message));
      }
    } catch (error) {
      dispatch(showToast("danger", error?.response?.data?.message));
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
      const datasets = getState().overview.datasets;

      const result = datasets.filter(
        (item) => item.resource_id !== dataset.resource_id
      );

      dispatch({
        type: TYPES.USER_RUNS,
        payload: result,
      });

      dispatch(initializeRuns());
      dispatch(showToast("success", "Deleted!"));
    }
  } catch (error) {
    dispatch(showToast("danger", error?.response?.data?.message));
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
      dispatch(showToast("success", toastMsg));
      dispatch(setSelectedRuns([]));
    } else {
      dispatch(showToast("warning", "Select dataset(s) for update"));
    }
  };

export const publishDataset =
  (dataset, updateValue) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      const endpoints = getState().apiEndpoint.endpoints;
      const savedRuns = getState().overview.savedRuns;

      const response = await API.post(
        `${endpoints?.api?.datasets_update}/${dataset.resource_id}?access=${updateValue}`
      );
      if (response.status === 200) {
        const dataIndex = savedRuns.findIndex(
          (item) => item.resource_id === dataset.resource_id
        );
        savedRuns[dataIndex].metadata[DATASET_ACCESS] = updateValue;

        dispatch({
          type: TYPES.SAVED_RUNS,
          payload: savedRuns,
        });
        dispatch(showToast("success", "Updated!"));
      }
    } catch (error) {
      dispatch(showToast("danger", error?.response?.data?.message));
      dispatch({ type: TYPES.NETWORK_ERROR });
    }
    dispatch({ type: TYPES.COMPLETED });
  };

export const setLoadingDoneFlag = () => async (dispatch, getState) => {
  const alreadyRendered = sessionStorage.getItem("loadingDone");

  setTimeout(() => {
    if (!alreadyRendered) {
      sessionStorage.setItem("loadingDone", true);
      dispatch({ type: TYPES.SET_LOADING_FLAG, payload: true });
    }
  }, DASHBOARD_LOAD_DELAY_MS);
};

const filterDatasetType = (type) => (getState) => {
  if (type === "newRuns") {
    return getState().overview.initNewRuns;
  }
  return getState().overview.savedRuns;
};

const updateDatasetType = (data, type) => (dispatch) => {
  if (type === "newRuns") {
    dispatch({
      type: TYPES.INIT_NEW_RUNS,
      payload: data,
    });
  } else {
    dispatch({
      type: TYPES.SAVED_RUNS,
      payload: data,
    });
  }
};
export const editMetadata =
  (value, metadata, rId, type) => async (dispatch, getState) => {
    const data = filterDatasetType(type)(getState);

    const rIndex = data.findIndex((item) => item.resource_id === rId);
    data[rIndex][metadata] = value;
    data[rIndex]["isDirty"] = true;
    if (value.length > DATASET_NAME_LENGTH) {
      data[rIndex]["name_validated"] = "error";
      data[rIndex][
        "name_errorMsg"
      ] = `Length should be < ${DATASET_NAME_LENGTH}`;
    } else {
      data[rIndex]["name_validated"] = "success";
    }
    dispatch(updateDatasetType(data, type));
  };

export const setRowtoEdit =
  (rId, isEdit, type) => async (dispatch, getState) => {
    const data = filterDatasetType(type)(getState);

    const rIndex = data.findIndex((item) => item.resource_id === rId);
    data[rIndex].isEdit = isEdit;

    if (!isEdit) {
      data[rIndex].name = data[rIndex]["name_copy"];
      data[rIndex]["isDirty"] = false;
    }
    dispatch(updateDatasetType(data, type));
  };
