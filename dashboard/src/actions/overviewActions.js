import * as CONSTANTS from "assets/constants/overviewConstants";
import * as TYPES from "./types";

import { DANGER, ERROR_MSG } from "assets/constants/toastConstants";

import API from "../utils/axiosInstance";
import Cookies from "js-cookie";
import { addParams } from "./datasetListActions";
import { clearCachedSession } from "./authActions";
import { findNoOfDays } from "utils/dateFunctions";
import { showToast } from "./toastActions";
import { uriTemplate } from "../utils/helper";

export const getDatasets = () => async (dispatch, getState) => {
  const alreadyRendered = getState().overview.loadingDone;
  const datasetType = getState().comparison.datasetType;

  const loggedIn = Cookies.get("isLoggedIn");
  try {
    if (alreadyRendered) {
      dispatch({ type: TYPES.LOADING });
    }
    const params = new URLSearchParams();

    addParams(params, loggedIn, datasetType);

    dispatch(setSelectedRuns([]));
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
    item[CONSTANTS.SERVER_DELETION_COPY] = item.metadata.server.deletion;

    clearEditableFields(item);
    item[CONSTANTS.NAME_VALIDATED] = CONSTANTS.SUCCESS;
    item[CONSTANTS.IS_ITEM_SEEN] = !!item?.metadata?.global?.dashboard?.seen;
    item[CONSTANTS.IS_ITEM_FAVORITED] =
      !!item?.metadata?.user?.dashboard?.favorite;
  });

  const savedRuns = data.filter(
    (item) => item.metadata.global?.dashboard?.saved
  );
  const newRuns = data.filter(
    (item) => !item.metadata.global?.dashboard?.saved
  );

  const expiringRuns = data.filter(
    (item) =>
      findNoOfDays(item.metadata.server.deletion) <
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
    payload: newRuns?.slice(0, CONSTANTS.DEFAULT_PER_PAGE_NEWRUNS) ?? [],
  });
  dispatch({
    type: TYPES.INIT_SAVED_RUNS,
    payload: savedRuns?.slice(0, CONSTANTS.DEFAULT_PER_PAGE_SAVED) ?? [],
  });
  dispatch({
    type: TYPES.INIT_EXPIRING_RUNS,
    payload: expiringRuns?.slice(0, CONSTANTS.DEFAULT_PER_PAGE_EXPIRING) ?? [],
  });
};
const metaDataActions = {
  save: CONSTANTS.DASHBOARD_SAVED,
  read: CONSTANTS.DASHBOARD_SEEN,
  favorite: CONSTANTS.USER_FAVORITE,
  datasetName: CONSTANTS.DATASET_NAME,
  serverDelete: CONSTANTS.SERVER_DELETION,
};
export const getMetaDataActions =
  (dataset, actionType, actionValue) => async (dispatch) => {
    const method = metaDataActions[actionType];
    const payload = { [method]: actionValue };
    return dispatch(updateDataset(dataset, payload));
  };
/**
 * Function which return a thunk to be passed to a Redux dispatch() call
 * @function
 * @param {Object} dataset - Dataset which is being updated
 * @param {Object} payload - Action (save, read, favorite, edit) being performed with the new value
 * @return {Function} - dispatch the action and update the state
 */

export const updateDataset =
  (dataset, payload) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });

      const runs = getState().overview.datasets;
      const endpoints = getState().apiEndpoint.endpoints;

      const uri = uriTemplate(endpoints, "datasets_metadata", {
        dataset: dataset.resource_id,
      });
      const response = await API.put(uri, {
        metadata: payload,
      });
      if (response.status === 200) {
        const item = runs.find(
          (item) => item.resource_id === dataset.resource_id
        );

        for (const key in response.data.metadata) {
          if (checkNestedPath(key, item.metadata)) {
            item.metadata = setValueFromPath(
              key,
              item.metadata,
              response.data.metadata[key]
            );
          } else if (item.metadata[key.split(".")[0]] === null) {
            assignKeyPath(
              item.metadata,
              key.split("."),
              response.data.metadata[key]
            );
          }
        }
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
 * @return {Function} - dispatch the action and update the state
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

export const setRows = (rows) => ({
  type: TYPES.INIT_NEW_RUNS,
  payload: rows,
});

export const setSavedRows = (rows) => ({
  type: TYPES.INIT_SAVED_RUNS,
  payload: rows,
});

export const setExpiringRows = (rows) => ({
  type: TYPES.INIT_EXPIRING_RUNS,
  payload: rows,
});
export const setSelectedRuns = (rows) => ({
  type: TYPES.SELECTED_NEW_RUNS,
  payload: rows,
});

export const setSelectedSavedRuns = (rows) => ({
  type: TYPES.SELECTED_SAVED_RUNS,
  payload: rows,
});
export const updateMultipleDataset =
  (method, value) => (dispatch, getState) => {
    const selectedRuns = getState().overview.selectedRuns;

    if (selectedRuns.length > 0) {
      selectedRuns.forEach((item) =>
        method === "delete"
          ? dispatch(deleteDataset(item))
          : dispatch(getMetaDataActions(item, method, value))
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
 *  @return {Function} - dispatch the action and update the state
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
        savedRuns[dataIndex].metadata.dataset.access = updateValue;

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
 * @return {Function} - dispatch the action and update the state
 */
export const editMetadata =
  (value, metadata, rId, type) => async (dispatch, getState) => {
    const data = filterDatasetType(type, getState);

    const rIndex = data.findIndex((item) => item.resource_id === rId);

    if (metadata === CONSTANTS.NAME_KEY) {
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
        data[rIndex][CONSTANTS.NAME_KEY] = value;
        data[rIndex][CONSTANTS.IS_DIRTY_NAME] = true;
      }
    } else if (metadata === CONSTANTS.SERVER_DELETION_KEY) {
      data[rIndex][CONSTANTS.IS_DIRTY_SERVER_DELETE] = true;
      data[rIndex].metadata.server.deletion = value;
    }
    dispatch(updateDatasetType(data, type));
  };
/**
 * Function which toggles the row of New runs or Saved runs Table to edit
 * @function
 * @param {string} rId - resource_id of the dataset which is being set to edit
 * @param {boolean} isEdit - Set/not set to edit
 * @param {string} type - Type of the Dataset (Saved/New)
 * @return {Function} - dispatch the action and update the state
 */
export const setRowtoEdit =
  (rId, isEdit, type) => async (dispatch, getState) => {
    const data = filterDatasetType(type, getState);

    const rIndex = data.findIndex((item) => item.resource_id === rId);
    data[rIndex][CONSTANTS.IS_EDIT] = isEdit;

    if (!isEdit) {
      data[rIndex].name = data[rIndex][CONSTANTS.NAME_COPY];
      data[rIndex].metadata.server.deletion =
        data[rIndex][CONSTANTS.SERVER_DELETION_COPY];
      clearEditableFields(data[rIndex]);
      data[rIndex][CONSTANTS.NAME_VALIDATED] = CONSTANTS.SUCCESS;
    }
    dispatch(updateDatasetType(data, type));
  };
/**
 * Function to get the metadata that are edited and to be sent for update
 * @function
 * @param {Object} dataset -  Dataset which is being updated
 * @param {string} type - Type of the Dataset (Saved/New)
 * @return {Function} - dispatch the action and update the state
 */
export const getEditedMetadata =
  (dataset, type) => async (dispatch, getState) => {
    const data = filterDatasetType(type, getState);

    const item = data.find((item) => item.resource_id === dataset.resource_id);

    const editedMetadata = {};
    if (item[CONSTANTS.IS_DIRTY_NAME]) {
      editedMetadata[metaDataActions[CONSTANTS.DATASET_NAME_KEY]] = item.name;
    }

    if (item[CONSTANTS.IS_DIRTY_SERVER_DELETE]) {
      editedMetadata[metaDataActions[CONSTANTS.SERVER_DELETION_KEY]] = new Date(
        item.metadata.server.deletion
      ).toISOString();
    }
    dispatch(updateDataset(dataset, editedMetadata));
  };

const clearEditableFields = (item) => {
  item[CONSTANTS.IS_DIRTY_NAME] = false;
  item[CONSTANTS.IS_DIRTY_SERVER_DELETE] = false;
};
export const setMetadataModal = (isOpen) => ({
  type: TYPES.SET_METADATA_MODAL,
  payload: isOpen,
});
/**
 * Function to get keySummary and send to parse data
 * @function
 * @param {Function} dispatch - dispatch method of redux store
 * @param {Function} getState -   getstate method of redux store
 * @return {Function} - dispatch the action and update the state
 */
export const getKeySummary = async (dispatch, getState) => {
  try {
    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.get(uriTemplate(endpoints, "datasets_list"), {
      params: { keysummary: true },
    });
    if (response.status === 200) {
      if (response.data.keys) {
        dispatch(parseKeySummaryforTree(response.data.keys));
      }
    }
  } catch (error) {
    dispatch(showToast(DANGER, ERROR_MSG));
  }
};
/**
 * Function to parse keySummary for the Tree View with checkboxes
 * @function
 * @param {Object} keySummary - dataset key summary
 * @return {Function} - dispatch the action and update the state
 */
export const parseKeySummaryforTree = (keySummary) => (dispatch, getState) => {
  const parsedData = [];

  const checkedItems = [...getState().overview.checkedItems];

  for (const [item, subitem] of Object.entries(keySummary)) {
    const dataObj = { title: item, options: [] };

    for (const [key, value] of Object.entries(subitem)) {
      const aggregateKey = `${item}${CONSTANTS.KEYS_JOIN_BY}${key}`;
      if (!isServerInternal(aggregateKey)) {
        const isChecked = checkedItems.includes(aggregateKey);
        const obj = constructTreeObj(aggregateKey, isChecked);
        if (value) {
          // has children
          obj["children"] = constructChildTreeObj(
            aggregateKey,
            value,
            checkedItems
          );
        }
        dataObj.options.push(obj);
      }
    }
    parsedData.push(dataObj);
  }
  dispatch({
    type: TYPES.SET_METADATA_CHECKED_KEYS,
    payload: checkedItems,
  });
  dispatch({
    type: TYPES.SET_TREE_DATA,
    payload: parsedData,
  });
};

const constructChildTreeObj = (aggregateKey, entity, checkedItems) => {
  const childObj = [];
  for (const item in entity) {
    if (!isServerInternal(`${aggregateKey}${CONSTANTS.KEYS_JOIN_BY}${item}`)) {
      const newKey = `${aggregateKey}${CONSTANTS.KEYS_JOIN_BY}${item}`;
      const isParentChecked = checkedItems.includes(aggregateKey);

      const isChecked = isParentChecked || checkedItems.includes(newKey);
      if (isParentChecked && !checkedItems.includes(newKey)) {
        checkedItems.push(newKey);
      }
      const obj = constructTreeObj(newKey, isChecked);

      if (entity[item]) {
        obj["children"] = constructChildTreeObj(
          newKey,
          entity[item],
          checkedItems
        );
      }
      childObj.push(obj);
    }
  }
  return childObj;
};

const constructTreeObj = (aggregateKey, isChecked) => ({
  name: aggregateKey.split(CONSTANTS.KEYS_JOIN_BY).pop(),
  key: aggregateKey,
  id: aggregateKey,
  checkProps: {
    "aria-label": `${aggregateKey}-check`,
    checked: isChecked,
  },
});

const nonEssentialKeys = [
  CONSTANTS.KEY_INDEX_REGEX,
  CONSTANTS.KEY_OPERATIONS_REGEX,
  CONSTANTS.KEY_TOOLS_REGEX,
  CONSTANTS.KEY_ITERATIONS_REGEX,
  CONSTANTS.KEY_TARBALL_PATH_REGEX,
];

const isServerInternal = (string) =>
  nonEssentialKeys.some((e) => string.match(e));

/**
 * Function to update metadata
 * @function
 * @param {String} path - nested key to update
 * @param {Object} obj - nested object
 * @param {String} value - new value to be updated in the object
 * @return {Object} - updated object with new value
 */

const setValueFromPath = (path, obj, value) => {
  const recurse = (plist, o, v) => {
    const [head, ...rest] = plist;
    return { ...o, [head]: rest.length ? recurse(rest, o[head], v) : v };
  };

  return recurse(path.split("."), obj, value);
};

/**
 * Function to check if the nested object has the given path of key
 * @function
 * @param {String} path - path of key
 * @param {Object} obj - nested object
 * @return {Boolean} - true/false if the object has/not the key
 */

const checkNestedPath = (path, obj = {}) =>
  path.split(".").reduce((a, p) => a?.[p], obj) !== undefined;

const assignKeyPath = (obj, keyPath, value) => {
  const lastKeyIndex = keyPath.length - 1;

  for (let i = 0; i < lastKeyIndex; ++i) {
    const key = keyPath[i];
    if (!(key in obj) || obj[key] === null) {
      obj[key] = {};
    }
    obj = obj[key];
  }
  obj[keyPath[lastKeyIndex]] = value;
};
