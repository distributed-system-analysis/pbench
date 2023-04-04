import * as CONSTANTS from "assets/constants/overviewConstants";
import * as TYPES from "./types";

import { DANGER, ERROR_MSG } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import { uriTemplate } from "../utils/helper";
import { findNoOfDays } from "utils/dateFunctions";
import { showToast } from "./toastActions";
import { clearCachedSession } from "./authActions";

export const getDatasets = () => async (dispatch, getState) => {
  const alreadyRendered = getState().overview.loadingDone;
  try {
    if (alreadyRendered) {
      dispatch({ type: TYPES.LOADING });
    }
    const params = new URLSearchParams();
    params.append("metadata", CONSTANTS.DASHBOARD_SAVED);
    params.append("metadata", CONSTANTS.DASHBOARD_SEEN);
    params.append("metadata", CONSTANTS.DATASET_ACCESS);
    params.append("metadata", CONSTANTS.DATASET_OWNER);
    params.append("metadata", CONSTANTS.DATASET_UPLOADED);
    params.append("metadata", CONSTANTS.SERVER_DELETION);
    params.append("metadata", CONSTANTS.USER_FAVORITE);

    params.append("mine", "true");

    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.get(uriTemplate(endpoints, "datasets_list"), {
      params,
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
    if (!error?.response) {
      dispatch(showToast(DANGER, "Not Authenticated"));
      dispatch({ type: TYPES.OPENID_ERROR });
      clearCachedSession(dispatch);
    } else {
      const msg = error.response?.data?.message;
      dispatch(showToast(DANGER, msg ? msg : `Error response: ERROR_MSG`));
      dispatch({ type: TYPES.NETWORK_ERROR });
    }
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
    item[CONSTANTS.IS_EDIT] = false;
    item[CONSTANTS.NAME_COPY] = item.name;
    item[CONSTANTS.IS_DIRTY] = false;
    item[CONSTANTS.NAME_VALIDATED] = CONSTANTS.DEFAULT;
    item[CONSTANTS.IS_ITEM_SEEN] = !!item?.metadata?.[CONSTANTS.DASHBOARD_SEEN];
    item[CONSTANTS.IS_ITEM_FAVORITED] =
      !!item?.metadata?.[CONSTANTS.USER_FAVORITE];
  });
  const defaultPerPage = getState().overview.defaultPerPage;

  const savedRuns = data.filter(
    (item) => item.metadata[CONSTANTS.DASHBOARD_SAVED]
  );
  const newRuns = data.filter(
    (item) => !item.metadata[CONSTANTS.DASHBOARD_SAVED]
  );

  const expiringRuns = data.filter(
    (item) =>
      findNoOfDays(item.metadata[CONSTANTS.SERVER_DELETION]) <
      CONSTANTS.EXPIRATION_DAYS_LIMIT
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
  save: CONSTANTS.DASHBOARD_SAVED,
  read: CONSTANTS.DASHBOARD_SEEN,
  favorite: CONSTANTS.USER_FAVORITE,
  datasetName: CONSTANTS.DATASET_NAME,
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
      const uri = uriTemplate(endpoints, "datasets_metadata", {
        dataset: dataset.resource_id,
      });
      const response = await API.put(uri, {
        metadata: { [method]: actionValue },
      });
      if (response.status === 200) {
        const dataIndex = runs.findIndex(
          (item) => item.resource_id === dataset.resource_id
        );
        runs[dataIndex].metadata[metaDataActions[actionType]] =
          response.data.metadata[metaDataActions[actionType]];
        dispatch({
          type: TYPES.USER_RUNS,
          payload: runs,
        });
        dispatch(initializeRuns());

        const errors = response.data?.errors;
        if (errors && Object.keys(errors).length > 0) {
          let errorText = "";

          for (const [key, value] of Object.entries(errors)) {
            errorText += `${key} : ${value} \n`;
          }
          dispatch(
            showToast("warning", "Problem updating metadata", errorText)
          );
        }
      } else {
        dispatch(showToast(DANGER, response?.data?.message ?? ERROR_MSG));
      }
    } catch (error) {
      dispatch(showToast(DANGER, error?.response?.data?.message));
      dispatch({ type: TYPES.NETWORK_ERROR });
    }
    dispatch({ type: TYPES.COMPLETED });
  };
/**
 * Function to delete the dataset
 * @function
 * @param {Object} dataset -  Dataset which is being updated *
 * @return {Object} - dispatch the action and update the state
 */
export const deleteDataset = (dataset) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.delete(
      uriTemplate(endpoints, "datasets", {
        dataset: dataset.resource_id,
      })
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
      dispatch(showToast(CONSTANTS.SUCCESS, "Deleted!"));
    }
  } catch (error) {
    dispatch(showToast(DANGER, error?.response?.data?.message ?? ERROR_MSG));
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

export const setSelectedSavedRuns = (rows) => {
  return {
    type: TYPES.SELECTED_SAVED_RUNS,
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
      dispatch(showToast(CONSTANTS.SUCCESS, toastMsg));
      dispatch(setSelectedRuns([]));
    } else {
      dispatch(showToast("warning", "Select dataset(s) for update"));
    }
  };
/**
 * Function to publish the dataset
 * @function
 * @param {Object} dataset -  Dataset which is being updated
 * @param {string} updateValue - Access type value (Public/Private)
 * @return {Object} - dispatch the action and update the state
 */
export const publishDataset =
  (dataset, updateValue) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      const endpoints = getState().apiEndpoint.endpoints;
      const savedRuns = getState().overview.savedRuns;

      const response = await API.post(
        uriTemplate(endpoints, "datasets", {
          dataset: dataset.resource_id,
        }),
        null,
        { params: { access: updateValue } }
      );
      if (response.status === 200) {
        const dataIndex = savedRuns.findIndex(
          (item) => item.resource_id === dataset.resource_id
        );
        savedRuns[dataIndex].metadata[CONSTANTS.DATASET_ACCESS] = updateValue;

        dispatch({
          type: TYPES.SAVED_RUNS,
          payload: savedRuns,
        });
        dispatch(showToast(CONSTANTS.SUCCESS, "Updated!"));
      }
    } catch (error) {
      dispatch(showToast(DANGER, error?.response?.data?.message ?? ERROR_MSG));
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
  }, CONSTANTS.DASHBOARD_LOAD_DELAY_MS);
};

const filterDatasetType = (type, getState) => {
  return type === "newRuns"
    ? getState().overview.initNewRuns
    : getState().overview.savedRuns;
};

const updateDatasetType = (data, type) => {
  return {
    type: type === "newRuns" ? TYPES.INIT_NEW_RUNS : TYPES.SAVED_RUNS,
    payload: data,
  };
};
/**
 * Function to validate the edited dataset
 * @function
 * @param {string} value - new value of the metadata that is being edited
 * @param {string} metadata - metadata that is being edited *
 * @param {string} rId - resource_id of the dataset which is being set to edit
 * @param {string} type - Type of the Dataset (Saved/New)
 * @return {Object} - dispatch the action and update the state
 */
export const editMetadata =
  (value, metadata, rId, type) => async (dispatch, getState) => {
    const data = filterDatasetType(type, getState);

    const rIndex = data.findIndex((item) => item.resource_id === rId);
    data[rIndex][metadata] = value;
    data[rIndex][CONSTANTS.IS_DIRTY] = true;
    if (value.length > CONSTANTS.DATASET_NAME_LENGTH) {
      data[rIndex][CONSTANTS.NAME_VALIDATED] = CONSTANTS.ERROR;
      data[rIndex][
        CONSTANTS.NAME_ERROR_MSG
      ] = `Length should be < ${CONSTANTS.DATASET_NAME_LENGTH}`;
    } else if (value.length === 0) {
      data[rIndex][CONSTANTS.NAME_VALIDATED] = CONSTANTS.ERROR;
      data[rIndex][CONSTANTS.NAME_ERROR_MSG] = `Length cannot be 0`;
    } else {
      data[rIndex][CONSTANTS.NAME_VALIDATED] = CONSTANTS.SUCCESS;
    }
    dispatch(updateDatasetType(data, type));
  };
/**
 * Function which toggles the row of New runs or Saved runs Table to edit
 * @function
 * @param {string} rId - resource_id of the dataset which is being set to edit
 * @param {boolean} isEdit - Set/not set to edit
 * @param {string} type - Type of the Dataset (Saved/New)
 * @return {Object} - dispatch the action and update the state
 */
export const setRowtoEdit =
  (rId, isEdit, type) => async (dispatch, getState) => {
    const data = filterDatasetType(type, getState);

    const rIndex = data.findIndex((item) => item.resource_id === rId);
    data[rIndex][CONSTANTS.IS_EDIT] = isEdit;

    if (!isEdit) {
      data[rIndex].name = data[rIndex][CONSTANTS.NAME_COPY];
      data[rIndex][CONSTANTS.IS_DIRTY] = false;
      data[rIndex][CONSTANTS.NAME_VALIDATED] = CONSTANTS.SUCCESS;
    }
    dispatch(updateDatasetType(data, type));
  };
