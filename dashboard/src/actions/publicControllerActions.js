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
        type: "GET_PUBLIC_CONTROLLERS",
        payload: response?.data,
      });
    }
    dispatch({ type: TYPES.COMPLETED });
  } catch (error) {
    return error;
  }
};

export const getFavoritedContollers = () => async (dispatch) => {
  let controllers = [];
  controllers = localStorage.getItem("favControllers")
    ? localStorage.getItem("favControllers")
    : [];
  dispatch({
    type: TYPES.FAVORITED_CONTROLLERS,
    payload: [...controllers],
  });
};

export const updateFavoriteRepoNames = (favorites) => async (dispatch) => {
    dispatch({
        type: TYPES.FAVORITED_CONTROLLERS,
        payload: [...favorites]
    })
};

export const updateTblData = (data) => async (dispatch) => {
  dispatch({
    type: TYPES.UPDATE_PUBLIC_CONTROLLERS,
    payload: [...data]
})
}