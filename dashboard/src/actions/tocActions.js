import * as TYPES from "./types";

import API from "utils/axiosInstance";
import { DANGER } from "assets/constants/toastConstants";
import { showToast } from "./toastActions";
import { uriTemplate } from "utils/helper";

/**
 * Function to fetch contents data
 * @function
 * @param {String} datasetId - Dataset ID
 * @param {String} dataUri - URI
 * @param {String} item - Active item
 * @param {Boolean} isSubDir - To identify sub-directory expansion
 * @return {Function} - dispatch the action and update the state
 */
export const fetchTOC =
  (datasetId, dataUri, item, isSubDir) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      const endpoints = getState().apiEndpoint.endpoints;
      const parent = dataUri?.split("contents/").pop();
      const uri = uriTemplate(endpoints, "datasets_contents", {
        dataset: datasetId,
        target: parent,
      });
      const response = await API.get(uri);
      if (response.status === 200 && response.data) {
        if (!isSubDir) {
          dispatch({
            type: TYPES.SET_INVENTORY_LINK,
            payload: response.data.uri.replace("contents", "inventory"),
          });
        }
        dispatch(parseToTreeView(response.data, item, isSubDir, parent));
      }
    } catch (error) {
      const msg = error.response?.data?.message;
      dispatch(showToast(DANGER, msg ?? `Error response: ${error}`));
    }
    dispatch({ type: TYPES.COMPLETED });
  };

/**
 * Function to parse contents data totree view
 * @function
 * @param {Object} contentData - Contentdata to parse
 * @param {Object} activeItem - Active item
 * @param {Boolean} isSubDir - To identify sub-directory expansion
 * @param {String} parent - Parent Name to set the id
 * @return {Function} - dispatch the action and update the state
 */
export const parseToTreeView =
  (contentData, activeItem, isSubDir, parent) => (dispatch, getState) => {
    const keyPath = parent.replaceAll("/", "*");
    const drillMenuData = [...getState().toc.drillMenuData];
    const treeOptions = contentData.directories.map((item) => {
      const obj = {
        name: item.name,
        id: parent ? `${keyPath}*${item.name}` : item.name,
        children: [],
        isDirectory: true,
        uri: item.uri,
      };
      return obj;
    });
    for (const item of contentData.files) {
      const obj = {
        name: item.name,
        id: parent ? `${keyPath}*${item.name}` : item.name,
        isDirectory: false,
        size: item.size,
        uri: item.uri,
      };
      treeOptions.push(obj);
    }
    if (isSubDir) {
      if (activeItem.includes("*")) {
        updateActiveItemChildren(drillMenuData, keyPath, treeOptions);
      } else {
        drillMenuData.forEach((item) => {
          if (item.name === activeItem.split("*").pop()) {
            item["children"] = treeOptions;
          }
        });
      }
    }
    dispatch({
      type: TYPES.SET_DRILL_MENU_DATA,
      payload: isSubDir ? drillMenuData : treeOptions,
    });
  };

/**
 * Function to find the actual key from key path and update it's children
 * @function
 * @param {Object} arr - Drill down menu
 * @param {String} key - key path
 * @param {Array} childrenToUpdate - Active item children obtained through API request
 * @return {Array} - updated children
 */
const updateActiveItemChildren = (arr, key, childrenToUpdate) => {
  // if children are undefined
  if (!arr) return;

  // loop over each entry and its children to find
  // entry with passed key
  arr.forEach((entry) => {
    if (entry.id === key) {
      entry.children = childrenToUpdate;
    }
    // recursive call to traverse children
    else {
      updateActiveItemChildren(entry.children, key, childrenToUpdate);
    }
  });

  return arr;
};

export const setActiveFileContent = (item) => ({
  type: TYPES.SET_ACTIVE_FILE,
  payload: item,
});
