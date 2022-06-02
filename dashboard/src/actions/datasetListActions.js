import * as TYPES from "./types";
import API from "../utils/api";

export const fetchPublicDatasets = () => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const response = await API.get(
      `${endpoints?.api?.datasets_list}?metadata=dataset.created&access=public`
    );
    if (response.status === 200 && response.data) {
      dispatch({
        type: "GET_PUBLIC_DATASETS",
        payload: response?.data,
      });
    }
    dispatch({ type: TYPES.COMPLETED });
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
