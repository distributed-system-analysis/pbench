import * as TYPES from "./types";

import API from "../utils/axiosInstance";
import { DANGER } from "assets/constants/toastConstants";
import { showToast } from "./toastActions";
import { uriTemplate } from "utils/helper";

export const fetchPublicDatasets = (page) => async (dispatch, getState) => {
  try {
    dispatch({ type: TYPES.LOADING });
    const endpoints = getState().apiEndpoint.endpoints;
    const { offset, limit, filter, searchKey, perPage } =
      getState().datasetlist;
    let publicData = [...getState().datasetlist.publicData];
    const params = new URLSearchParams();
    params.append("metadata", "dataset.uploaded");
    params.append("access", "public");
    params.append("offset", offset);
    params.append("limit", limit);

    if (searchKey) {
      params.append("name", searchKey);
    }
    if (filter.startDate instanceof Date && !isNaN(filter.startDate)) {
      params.append("start", new Date(filter.startDate).toUTCString());
    }
    if (filter.endDate instanceof Date && !isNaN(filter.endDate)) {
      params.append("end", new Date(filter.endDate).toUTCString());
    }

    const response = await API.get(
      uriTemplate(endpoints, "datasets_list", {}),
      {
        params,
      }
    );

    if (response.status === 200 && response.data) {
      const startIdx = (page - 1) * perPage;

      if (publicData.length === 0) {
        publicData = new Array(response.data.total);
      }
      publicData.splice(
        startIdx,
        response.data.results.length,
        ...response.data.results
      );

      dispatch({
        type: TYPES.GET_PUBLIC_DATASETS,
        payload: [...publicData],
      });
      // in case of last page, next_url is empty
      if (response.data.next_url) {
        const urlSearchParams = new URLSearchParams(response.data.next_url);
        const params = Object.fromEntries(urlSearchParams.entries());

        dispatch({
          type: TYPES.SET_PAGE_OFFSET,
          payload: Number(params?.offset),
        });
      }
      dispatch({
        type: TYPES.SET_TOTAL_DATASETS,
        payload: response.data?.total,
      });
    }
  } catch (error) {
    dispatch(showToast(DANGER, "Error"));
    dispatch({ type: TYPES.NETWORK_ERROR });
  }
  dispatch({ type: TYPES.COMPLETED });
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

export const setPageLimit = (newPerPage) => async (dispatch) => {
  dispatch({
    type: TYPES.SET_PAGE_LIMIT,
    payload: newPerPage,
  });
};

export const setFilterKeys = (startDate, endDate) => async (dispatch) => {
  dispatch({
    type: TYPES.SET_DATE_RANGE,
    payload: { startDate, endDate },
  });
};

export const nameFilter = (value) => async (dispatch) => {
  dispatch({
    type: TYPES.SET_SEARCH_KEY,
    payload: value,
  });
};

export const applyFilter = () => (dispatch) => {
  dispatch({
    type: TYPES.GET_PUBLIC_DATASETS,
    payload: [],
  });
  dispatch({
    type: TYPES.SET_PAGE_OFFSET,
    payload: 0,
  });
  dispatch(fetchPublicDatasets(1));
};

export const setPerPage = (value) => (dispatch) => {
  dispatch({
    type: TYPES.SET_PER_PAGE,
    payload: value,
  });
};
