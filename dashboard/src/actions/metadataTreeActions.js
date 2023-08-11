import * as TYPES from "./types";

import store from "store/store";

const { getState } = store;

// Helper functions
const isChecked = (dataItem, checkedItems) =>
  checkedItems && checkedItems.some((item) => item === dataItem.key);
const areAllDescendantsChecked = (dataItem, checkedItems) =>
  dataItem.children
    ? dataItem.children.every((child) =>
        areAllDescendantsChecked(child, checkedItems)
      )
    : isChecked(dataItem, checkedItems);
const areSomeDescendantsChecked = (dataItem, checkedItems) =>
  dataItem.children
    ? dataItem.children.some((child) =>
        areSomeDescendantsChecked(child, checkedItems)
      )
    : isChecked(dataItem, checkedItems);
const setTreeViewChecked = (childNodes, isChecked) => {
  childNodes.forEach(function iter(a) {
    a.checkProps.checked = isChecked;
    Array.isArray(a.children) && a.children.forEach(iter);
  });
};
const getCheckedItemsKey = (ary) =>
  ary.reduce(
    (a, b) =>
      a.concat(b.key, "children" in b ? getCheckedItemsKey(b.children) : []),
    []
  );
const updateChildKeysList = (checked, checkedItems, childKeys) =>
  checked
    ? [...checkedItems, ...childKeys]
    : checkedItems.filter((x) => !childKeys.includes(x));

export const mapTree = (item) => {
  const checkedItems = getState().overview.checkedItems;

  item.checkProps.checked = areAllDescendantsChecked(item, checkedItems);
  if (
    !item.checkProps.checked &&
    areSomeDescendantsChecked(item, checkedItems)
  ) {
    item.checkProps.checked = null;
  }

  const retVal = { ...item };
  if (item.children) {
    retVal.children = item.children.map((child) => mapTree(child));
  }
  return retVal;
};

export const onCheck =
  (evt, treeViewItem, dataType) => async (dispatch, getState) => {
    const checked = evt.target.checked;
    const treeData = [...getState().overview.treeData];
    let checkedItems = getState().overview.checkedItems;
    const { options } = treeData.find((item) => item.title === dataType);
    if ("children" in treeViewItem) {
      const childNodes = treeViewItem.children;
      const childKeys = getCheckedItemsKey(childNodes);

      setTreeViewChecked(childNodes, checked);
      treeViewItem.checkProps.checked = checked;

      checkedItems = updateChildKeysList(checked, checkedItems, childKeys);
    } else if ("children" in options[0]) {
      // if first child
      const childNodes = options[0]["children"];
      const node = childNodes.find((item) => item.key === treeViewItem.key);
      node.checkProps.checked = checked;
      // if only child of the parent, push the parent
      if (childNodes.length === 1) {
        options[0].checkProps.checked = checked;

        checkedItems = updateChildKeysList(
          checked,
          checkedItems,
          options[0].key
        );
      }
    } else {
      // leaf node
      const node = options.find((item) => treeViewItem.key.includes(item.key));
      node.checkProps.checked = checked;
    }
    if (checked) {
      checkedItems = [...checkedItems, treeViewItem.key];
    } else {
      checkedItems = checkedItems.filter((item) => item !== treeViewItem.key);
    }
    dispatch({
      type: TYPES.SET_TREE_DATA,
      payload: treeData,
    });
    dispatch({
      type: TYPES.SET_METADATA_CHECKED_KEYS,
      payload: checkedItems,
    });
  };
