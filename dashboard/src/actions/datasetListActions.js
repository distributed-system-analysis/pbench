import * as TYPES from "./types";
import API from "../utils/api";

export const fetchPublicDatasets = () => async (dispatch) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const response = await API.get(
      "api/v1/datasets/list?metadata=dataset.created&access=public"
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
  let fav_datasets = [];
  let fav_datasets_text = localStorage.getItem("favorite_datasets");
  fav_datasets = fav_datasets_text ? JSON.parse(fav_datasets_text) : [];
  dispatch({
    type: TYPES.FAVORITED_DATASETS,
    payload: [...fav_datasets],
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
