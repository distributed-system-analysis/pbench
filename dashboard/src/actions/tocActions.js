import * as TYPES from "./types";

import API from "utils/axiosInstance";
import { DANGER } from "assets/constants/toastConstants";
import { showToast } from "./toastActions";
import { uriTemplate } from "utils/helper";

/**
 * Function to fetch contents data
 * @function
 * @param {String} datasetId - Dataset ID
 * @param {String} path - Path to the file/directory
 * @param {String} item - Active item
 * @param {Boolean} isSubDir - To identify sub-directory expansion
 * @return {Function} - dispatch the action and update the state
 */
export const fetchTOC =
  (datasetId, path, item, isSubDir) => async (dispatch, getState) => {
    try {
      dispatch({ type: TYPES.LOADING });
      const endpoints = getState().apiEndpoint.endpoints;

      const uri = uriTemplate(endpoints, "datasets_contents", {
        dataset: datasetId,
        target: path,
      });
      const response = await API.get(uri);
      if (response.status === 200 && response.data) {
        if (!isSubDir) {
          const inventoryLink = uriTemplate(endpoints, "datasets_inventory", {
            dataset: datasetId,
            target: path,
          });
          dispatch({
            type: TYPES.SET_INVENTORY_LINK,
            payload: inventoryLink,
          });
        }
        dispatch(parseToTreeView(response.data, item, isSubDir, path));
      }
    } catch (error) {
      const msg = error.response?.data?.message;
      dispatch(showToast(DANGER, msg ?? `Error response: ${error}`));
    }
    dispatch({ type: TYPES.COMPLETED });
  };

const makeOptions = (data, isParent, keyPath, isDirectory) => {
  const options = data.map((item) => {
    const option = {
      name: item.name,
      id: isParent ? `${keyPath}*${item.name}` : item.name,
      isDirectory,
      uri: item.uri,
    };
    if (isDirectory) {
      option.children = [];
    } else {
      option.size = item.size;
    }
    return option;
  });
  return options;
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
    const directories = makeOptions(
      contentData.directories,
      parent,
      keyPath,
      true
    );
    const files = makeOptions(contentData.files, parent, keyPath, false);
    const treeOptions = [...directories, ...files];
    if (isSubDir) {
      if (activeItem.includes("*")) {
        updateActiveItemChildren(drillMenuData, keyPath, treeOptions);
      } else {
        const itemName = activeItem.split("*").pop();
        const itemOptions = drillMenuData.find((i) => i.name === itemName);
        if (itemOptions) {
          itemOptions["children"] = treeOptions;
        }
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
