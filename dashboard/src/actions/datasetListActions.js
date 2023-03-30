import * as TYPES from "./types";

import API from "../utils/axiosInstance";
import { uriTemplate } from "utils/helper";

export const fetchPublicDatasets = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.get(
      uriTemplate(endpoints, "datasets_list", {}),
      null,
      { params: { metadata: "dataset.uploaded", access: "public" } }
    );
    if (response.status === 200 && response.data) {
      dispatch({
        type: "GET_PUBLIC_DATASETS",
        payload: response?.data?.results,
      });
    }
    dispatch({ type: TYPES.COMPLETED });
    dispatch(callLoading());
  } catch (error) {
    return error;
  }
};

export const getFavoritedDatasets = () => async (dispatch) => {
  const favDatasetsText = localStorage.getItem("favorite_datasets");
  const favDatasets = favDatasetsText ? JSON.parse(favDatasetsText) : [];
  dispatch({
    type: TYPES.FAVORITED_DATASETS,
    payload: favDatasets,
  });
};

export const updateFavoriteRepoNames = (favorites) => async (dispatch) => {
  dispatch({
    type: TYPES.FAVORITED_DATASETS,
    payload: [...favorites],
  });
};

export const updateTblData = (data) => async (dispatch) => {
  dispatch({
    type: TYPES.UPDATE_PUBLIC_DATASETS,
    payload: [...data],
  });
};

export const callLoading = () => (dispatch) => {
  dispatch({ type: TYPES.LOADING });
  setTimeout(() => {
    dispatch({ type: TYPES.COMPLETED });
  }, 5000);
};
