import * as TYPES from "./types";
import API from "../utils/axiosInstance";

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

    const request = {
      params: params,
    };
    const endpoints = getState().apiEndpoint.endpoints;
    const defaultPerPage = getState().overview.defaultPerPage;

    const response = await API.get(endpoints?.api?.datasets_list, {
      ...request,
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
    dispatch({ type: TYPES.COMPLETED });
  } catch (error) {
    dispatch(constructToast("danger", error?.response?.data?.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
    dispatch({ type: TYPES.COMPLETED });
  }
};

export const updateDataset =
  (dataset, actionType, updateAction) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      const actions = {
        save: "dashboard.saved",
        read: "dashboard.seen",
        favorite: "user.favorite",
      };
      const savedRuns = getState().overview.savedRuns;
      const newRuns = getState().overview.newRuns;
      const method = actions[actionType];
      const metadata = { [method]: updateAction };
      const params = {
        name: dataset.name,
        metadata,
      };
      const dataIndex = newRuns.findIndex(
        (item) => item.resource_id === dataset.resource_id
      );
      const endpoints = getState().apiEndpoint.endpoints;
      const response = await API.put(
        `${endpoints?.api?.datasets_metadata}/${dataset.resource_id}`,
        {
          ...params,
        }
      );
      if (response.status === 200) {
        if (actionType === "save") {
          savedRuns.push(dataset);
          const filteredNewRuns = newRuns.filter(
            (item) => item.resource_id !== dataset.resource_id
          );
          dispatch({
            type: TYPES.SAVED_RUNS,
            payload: savedRuns,
          });
          dispatch({
            type: TYPES.NEW_RUNS,
            payload: filteredNewRuns,
          });
        } else if (actionType === "read") {
          newRuns[dataIndex].metadata["dashboard.seen"] =
            response.data["dashboard.seen"];
          dispatch({
            type: TYPES.NEW_RUNS,
            payload: newRuns,
          });
        } else if (actionType === "favorite") {
          newRuns[dataIndex].metadata["user.favorite"] =
            response.data["user.favorite"];
          dispatch({
            type: TYPES.NEW_RUNS,
            payload: newRuns,
          });
        }
      } else {
        dispatch(constructToast("danger", response?.data?.message));
      }
      dispatch({ type: TYPES.COMPLETED });
    } catch (error) {
      dispatch(constructToast("danger", error?.response?.data?.message));
      dispatch({ type: TYPES.NETWORK_ERROR });
      dispatch({ type: TYPES.COMPLETED });
    }
  };

export const deleteDataset = (dataset) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const datasets = getState().overview.newRuns;
    const params = { name: dataset.name };
    const response = await API.post(
      `${endpoints?.api?.datasets_delete}/${dataset.resource_id}`,
      {
        ...params,
      }
    );
    if (response.status === 200) {
      const result = datasets.filter(
        (item) => item.resource_id !== dataset.resource_id
      );
      await dispatch({
        type: TYPES.NEW_RUNS,
        payload: result,
      });
      dispatch(constructToast("success", "Deleted!"));
    }
    dispatch({ type: TYPES.COMPLETED });
  } catch (error) {
    dispatch(constructToast("danger", error?.response?.data?.message));
    dispatch({ type: TYPES.NETWORK_ERROR });
    dispatch({ type: TYPES.COMPLETED });
  }
};

export const setRows = (rows) => async (dispatch) => {
  dispatch({
    type: TYPES.INIT_NEW_RUNS,
    payload: rows,
  });
};

export const setSelectedRuns = (rows) => async (dispatch) => {
  dispatch({
    type: TYPES.SELECTED_NEW_RUNS,
    payload: rows,
  });
};

export const updateMultipleDataset = (method) => async (dispatch, getState) => {
  const selectedRuns = getState().overview.selectedRuns;
  let toastMsg = "";
  if (selectedRuns > 0) {
    if (method === "delete") {
      selectedRuns.forEach((item) => {
        dispatch(deleteDataset(item));
      });
      toastMsg = "Deleted!";
    } else {
      selectedRuns.forEach((item) => {
        dispatch(updateDataset(item, method, true));
      });
      toastMsg = method === "save" ? "Saved!" : "Updated!";
    }

    dispatch(constructToast("success", toastMsg));
    dispatch(setSelectedRuns([]));
  } else {
    dispatch(constructToast("warning", "Select dataset(s) for update"));
  }
};
